"""Append-only, in-memory ledger core.

The whole design in three lines:

1. The ledger is a list of postings. Records are frozen and only ever appended.
2. A balance is the sum of an account's postings up to a value date.
3. Closing a day charges overdraft fees, accrues interest and, on the last
   day, pays the accrued interest in.

Everything else here is the handling of each event type.
"""

from dataclasses import dataclass
from decimal import Decimal

from .config import DAILY_INTEREST_RATE, OVERDRAFT_FEE, WINDOW_DAYS
from .money import MoneyError, fmt, parse_amount, split_evenly, to_money

ZERO = Decimal(0)

# Posting kinds. The first five are also the event types.
CREDIT = "CREDIT"
DEBIT = "DEBIT"
REVERSAL = "REVERSAL"
AUTHORIZATION = "AUTHORIZATION"
SETTLEMENT = "SETTLEMENT"
FORCE_POST = "FORCE_POST"
FEE = "FEE"
INTEREST = "INTEREST"

# Authorization states.
APPROVED = "APPROVED"
DECLINED = "DECLINED"
SETTLED = "SETTLED"

ERROR = "ERROR"      # event refused, nothing posted
WARNING = "WARNING"  # event applied, but flagged

SYSTEM = "SYSTEM"    # event_id of postings the ledger makes itself


# ---- records: all frozen, all append-only (R4) ---------------------------

@dataclass(frozen=True)
class Event:
    """An instruction from the stream, exactly as received."""

    id: str
    booked_day: int
    type: str
    account: str
    currency: str = None
    amount: object = None
    value_date: int = None
    auth_id: str = None
    reverses: str = None
    instalments: int = 1


@dataclass(frozen=True)
class Posting:
    """One signed movement on an account's ledger balance."""

    account: str
    kind: str
    amount: Decimal
    booked_day: int
    value_date: int
    event_id: str
    for_day: int = None    # fees only: the negative day being charged
    reverses: str = None   # reversals only: the event being reversed


@dataclass(frozen=True)
class AuthRecord:
    """One step in an authorization's life. The latest record is its state."""

    account: str
    auth_id: str
    state: str
    hold: Decimal
    settled: Decimal
    day: int
    event_id: str
    reason: str


@dataclass(frozen=True)
class DayClose:
    """The figures for one account as known when a day was closed."""

    account: str
    day: int
    closing_before_fees: Decimal
    closing: Decimal
    available: Decimal
    fee_days: tuple
    accrued: Decimal        # interest accrued at this close (can be negative)
    accrued_total: Decimal  # sum of all accruals so far
    capitalized: Decimal    # interest paid in at this close (last day only)


@dataclass(frozen=True)
class Notice:
    day: int
    account: str
    event_id: str
    severity: str
    code: str
    message: str


class Rejected(Exception):
    """Raised to refuse an event; recorded as an ERROR notice."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# ---- the ledger ----------------------------------------------------------

class Ledger:
    def __init__(self, accounts, last_day=WINDOW_DAYS, overdraft_fee=None, daily_rate=DAILY_INTEREST_RATE):
        """accounts maps account id -> currency. Opening balances are zero."""
        self.accounts = dict(accounts)
        self.last_day = last_day
        self._overdraft_fee = OVERDRAFT_FEE if overdraft_fee is None else overdraft_fee
        self._daily_rate = daily_rate
        self._events = []
        self._postings = []
        self._auths = []
        self._closes = []
        self._notices = []

    # The logs are handed out as tuples so callers cannot alter them.
    events = property(lambda self: tuple(self._events))
    postings = property(lambda self: tuple(self._postings))
    auth_records = property(lambda self: tuple(self._auths))
    closes = property(lambda self: tuple(self._closes))
    notices = property(lambda self: tuple(self._notices))

    # ---- balances --------------------------------------------------------

    def balance(self, account, day=None):
        """Ledger balance: all postings with value_date <= day (R1)."""
        day = self.last_day if day is None else day
        zero = to_money(ZERO, self.accounts[account])
        return sum((p.amount for p in self._postings if p.account == account and p.value_date <= day), zero)

    def auth_states(self, account, day=None):
        """Latest record per authorization, as known at the end of `day`."""
        day = self.last_day if day is None else day
        return {r.auth_id: r for r in self._auths if r.account == account and r.day <= day}

    def holds(self, account):
        """Total of active holds: approved and not yet settled."""
        zero = to_money(ZERO, self.accounts[account])
        return sum((r.hold for r in self.auth_states(account).values() if r.state == APPROVED), zero)

    def available(self, account, day=None):
        """Available balance: ledger balance minus active holds (R5)."""
        return self.balance(account, day) - self.holds(account)

    # ---- events ----------------------------------------------------------

    def apply(self, event):
        """Apply one event. Returns False if it was refused (nothing is posted)."""
        handlers = {
            CREDIT: self._credit_or_debit,
            DEBIT: self._credit_or_debit,
            REVERSAL: self._reverse,
            AUTHORIZATION: self._authorize,
            SETTLEMENT: self._settle,
        }
        try:
            if event.account not in self.accounts:
                raise Rejected("UNKNOWN_ACCOUNT", f"unknown account {event.account!r}")
            if event.currency not in (None, self.accounts[event.account]):
                raise Rejected("CURRENCY_MISMATCH", f"{event.currency} event on {event.account}")
            if event.type not in handlers:
                raise Rejected("UNKNOWN_EVENT_TYPE", f"unknown event type {event.type!r}")
            handlers[event.type](event)
        except Rejected as r:
            self._notice(event, ERROR, r.code, r.message)
            return False
        self._events.append(event)
        return True

    def _credit_or_debit(self, event):
        sign = 1 if event.type == CREDIT else -1
        try:
            parts = split_evenly(self._amount(event), event.instalments, self.accounts[event.account])
        except MoneyError as e:
            raise Rejected("INVALID_AMOUNT", str(e)) from None
        for part in parts:
            self._post(event.account, event.type, sign * part, event.booked_day, event.value_date, event.id)

    def _reverse(self, event):
        """Undo a credit or debit by appending the opposite postings (R4)."""
        originals = [
            p for p in self._postings
            if p.event_id == event.reverses and p.account == event.account and p.kind in (CREDIT, DEBIT)
        ]
        if not originals:
            raise Rejected("REVERSAL_TARGET_NOT_FOUND", f"{event.reverses} is not a credit or debit on {event.account}")
        if any(p.reverses == event.reverses for p in self._postings):
            raise Rejected("ALREADY_REVERSED", f"{event.reverses} was already reversed")
        for p in originals:
            self._post(
                event.account, REVERSAL, -p.amount, event.booked_day, event.value_date, event.id,
                reverses=event.reverses,
            )

    def _authorize(self, event):
        """Approve only if available balance stays >= 0 after the hold (R5).

        A decline is a decision, not an error: it is recorded as a state.
        """
        amount = self._amount(event)
        after = self.available(event.account, event.booked_day) - amount
        money = fmt(after, self.accounts[event.account])
        if after >= 0:
            self._auth(event, APPROVED, amount, ZERO, f"available after hold {money}")
        else:
            self._auth(event, DECLINED, amount, ZERO, f"available after hold would be {money}")

    def _settle(self, event):
        """Post a settlement and release its hold.

        A settlement reports money that has already moved. If there is no
        active hold to match it, the ledger still posts it (a force-post) and
        flags it, because refusing would leave the ledger wrong about the
        account. See REJECTED.md, C4.
        """
        amount = self._amount(event)
        currency = self.accounts[event.account]
        auth = self.auth_states(event.account).get(event.auth_id)
        if auth is not None and auth.state == APPROVED:
            self._post(event.account, SETTLEMENT, -amount, event.booked_day, event.value_date, event.id)
            self._auth(event, SETTLED, auth.hold, amount, f"hold {fmt(auth.hold, currency)} released")
        else:
            self._post(event.account, FORCE_POST, -amount, event.booked_day, event.value_date, event.id)
            self._notice(
                event, WARNING, "UNMATCHED_SETTLEMENT",
                f"{event.auth_id} has no active hold; {fmt(amount, currency)} force-posted for dispute",
            )

    def _amount(self, event):
        try:
            amount = parse_amount(event.amount, self.accounts[event.account])
        except MoneyError as e:
            raise Rejected("INVALID_AMOUNT", str(e)) from None
        if amount <= 0:
            raise Rejected("INVALID_AMOUNT", f"amount must be positive, got {amount}")
        return amount

    # ---- end of day ------------------------------------------------------

    def close_day(self, day):
        """Close `day` for every account: fees, then interest, then capitalization."""
        for account, currency in self.accounts.items():
            before_fees = self.balance(account, day)
            fee_days = self._charge_overdraft_fees(account, day)
            accrued, total = self._accrue_interest(account, day)
            capitalized = to_money(ZERO, currency)
            if day == self.last_day and total > 0:
                capitalized = total
                self._post(account, INTEREST, total, day, day, SYSTEM)
            self._closes.append(
                DayClose(
                    account=account,
                    day=day,
                    closing_before_fees=before_fees,
                    closing=self.balance(account, day),
                    available=self.available(account, day),
                    fee_days=fee_days,
                    accrued=accrued,
                    accrued_total=total,
                    capitalized=capitalized,
                )
            )

    def _charge_overdraft_fees(self, account, day):
        """Charge each day whose closing balance is negative, once (R1).

        Every day up to today is checked, so a backdated entry that turns an
        earlier day negative is charged when it becomes known. The fee is
        booked today with today's value date, whichever day it is for.
        """
        fee = self._overdraft_fee.get(self.accounts[account])
        if fee is None:
            return ()
        charged = {p.for_day for p in self._postings if p.account == account and p.kind == FEE}
        fee_days = []
        for d in range(1, day + 1):
            if d not in charged and self.balance(account, d) < 0:
                self._post(account, FEE, -fee, day, day, SYSTEM, for_day=d)
                fee_days.append(d)
        return tuple(fee_days)

    def _accrue_interest(self, account, day):
        """Interest on positive closing balances (R2). Returns (today, total).

        The running total is rounded, not each day: today's accrual is the
        rounded interest for all days so far, as now known, minus what was
        accrued before. So nothing is lost to rounding, the accruals always
        sum to the total, and backdated entries restate earlier days.
        """
        exact = sum(max(self.balance(account, d), ZERO) * self._daily_rate for d in range(1, day + 1))
        total = to_money(exact, self.accounts[account])
        already = sum((c.accrued for c in self._closes if c.account == account), ZERO)
        return total - already, total

    # ---- append helpers --------------------------------------------------

    def _post(self, account, kind, amount, booked_day, value_date, event_id, *, for_day=None, reverses=None):
        self._postings.append(Posting(account, kind, amount, booked_day, value_date, event_id, for_day, reverses))

    def _auth(self, event, state, hold, settled, reason):
        self._auths.append(
            AuthRecord(event.account, event.auth_id, state, hold, settled, event.booked_day, event.id, reason)
        )

    def _notice(self, event, severity, code, message):
        self._notices.append(Notice(event.booked_day, event.account, event.id, severity, code, message))
