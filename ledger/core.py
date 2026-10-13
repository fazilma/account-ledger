"""Append-only, in-memory ledger core.

Every list held by the Ledger only ever grows, and every record in those
lists is a frozen dataclass. State (balances, reversal status) is always
derived by folding the logs, never stored and updated in place.
"""

from dataclasses import dataclass
from decimal import Decimal

from .config import DAILY_INTEREST_RATE, OVERDRAFT_FEE, WINDOW_DAYS
from .money import MoneyError, fmt, parse_amount, split_evenly, to_money

ZERO = Decimal(0)

CREDIT = "CREDIT"
DEBIT = "DEBIT"
REVERSAL = "REVERSAL"
AUTHORIZATION = "AUTHORIZATION"
SETTLEMENT = "SETTLEMENT"
FORCE_POST = "FORCE_POST"
FEE = "FEE"
INTEREST = "INTEREST"

SYSTEM = "SYSTEM"

APPROVED = "APPROVED"
DECLINED = "DECLINED"
SETTLED = "SETTLED"

ERROR = "ERROR"
WARNING = "WARNING"


@dataclass(frozen=True)
class Event:
    """An instruction received from the stream, exactly as received."""

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

    seq: int
    account: str
    kind: str
    amount: Decimal
    booked_day: int
    value_date: int
    event_id: str
    for_day: int = None
    reverses: str = None
    note: str = ""


@dataclass(frozen=True)
class AuthRecord:
    """One step in an authorization's life. The latest record is its state."""

    seq: int
    account: str
    auth_id: str
    state: str
    hold: Decimal
    settled: Decimal
    day: int
    event_id: str
    reason: str = ""


@dataclass(frozen=True)
class Accrual:
    """Interest accrued at one day close. Not a balance movement until capitalized.

    amount is the rounded cumulative interest for all days so far, as the
    ledger sees them at this close, minus everything accrued before. It
    therefore carries both the rounding remainder and any restatement caused
    by backdated entries, and the amounts always sum to rounded_cumulative.
    """

    seq: int
    account: str
    day: int
    amount: Decimal
    own_day_exact: Decimal
    exact_cumulative: Decimal
    rounded_cumulative: Decimal


@dataclass(frozen=True)
class DayClose:
    """Snapshot taken when a day is closed: the figures as known at that time."""

    seq: int
    account: str
    day: int
    closing_before_fees: Decimal
    closing: Decimal
    available: Decimal
    fee_days: tuple
    accrued: Decimal
    capitalized: Decimal


@dataclass(frozen=True)
class Notice:
    """An error (event refused) or warning (event applied, but flagged)."""

    seq: int
    day: int
    account: str
    event_id: str
    severity: str
    code: str
    message: str


class Rejected(Exception):
    """Raised inside the ledger to refuse an event; becomes an ERROR notice."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Ledger:
    def __init__(self, accounts, last_day=WINDOW_DAYS, overdraft_fee=None, daily_rate=DAILY_INTEREST_RATE):
        """accounts maps account id -> currency. Opening balances are zero."""
        self._accounts = dict(accounts)
        self._last_day = last_day
        self._overdraft_fee = dict(OVERDRAFT_FEE if overdraft_fee is None else overdraft_fee)
        self._daily_rate = daily_rate
        self._events = []
        self._postings = []
        self._auths = []
        self._accruals = []
        self._closes = []
        self._notices = []

    # ---- read side -------------------------------------------------------

    @property
    def events(self):
        return tuple(self._events)

    @property
    def postings(self):
        return tuple(self._postings)

    @property
    def notices(self):
        return tuple(self._notices)

    @property
    def accounts(self):
        return dict(self._accounts)

    def currency(self, account):
        return self._accounts[account]

    def balance(self, account, day=None):
        """Ledger balance: all postings with value_date <= day (R1)."""
        day = self._last_day if day is None else day
        return sum(
            (p.amount for p in self._postings if p.account == account and p.value_date <= day),
            self._zero(account),
        )

    def _zero(self, account):
        """Zero at the account currency's precision, so empty sums keep it (R3)."""
        return to_money(ZERO, self._accounts[account])

    @property
    def auth_records(self):
        return tuple(self._auths)

    @property
    def accruals(self):
        return tuple(self._accruals)

    @property
    def closes(self):
        return tuple(self._closes)

    @property
    def last_day(self):
        return self._last_day

    def closed_through(self, account):
        return max((c.day for c in self._closes if c.account == account), default=0)

    def auth_states(self, account, day=None):
        """Latest record per authorization, as known at the end of `day`."""
        day = self._last_day if day is None else day
        latest = {}
        for r in self._auths:
            if r.account == account and r.day <= day:
                latest[r.auth_id] = r
        return latest

    def holds(self, account):
        """Total of active holds: authorizations approved and not yet settled."""
        return sum(
            (r.hold for r in self.auth_states(account).values() if r.state == APPROVED),
            self._zero(account),
        )

    def available(self, account, day=None):
        """Available balance: ledger balance minus active holds (R5)."""
        return self.balance(account, day) - self.holds(account)

    # ---- write side ------------------------------------------------------

    def apply(self, event):
        """Apply one event. Returns True if accepted, False if refused.

        A refused event leaves no posting; the refusal itself is recorded.
        """
        try:
            self._validate(event)
            # Days before the event's booking day are over for this account.
            late = event.booked_day <= self.closed_through(event.account)
            self._close_through(event.account, event.booked_day - 1)
            handler = self._handlers().get(event.type)
            if handler is None:
                raise Rejected("UNKNOWN_EVENT_TYPE", f"unknown event type {event.type!r}")
            handler(event)
        except Rejected as r:
            self._notice(event, ERROR, r.code, r.message)
            return False
        self._events.append(event)
        if late:
            self._notice(
                event, WARNING, "LATE_BOOKING",
                f"booked on Day {event.booked_day}, which was already closed; picked up at the next close",
            )
        return True

    def finish(self):
        """Close every remaining day for every account, through the last day."""
        for account in self._accounts:
            self._close_through(account, self._last_day)

    def _close_through(self, account, day):
        for d in range(self.closed_through(account) + 1, day + 1):
            self.close_day(account, d)

    def close_day(self, account, day):
        """End-of-day run for one account: fee sweep, interest, capitalization."""
        if day != self.closed_through(account) + 1 or day > self._last_day:
            raise ValueError(f"cannot close Day {day} for {account}: days close once, in order")
        currency = self._accounts[account]
        closing_before_fees = self.balance(account, day)
        fee_days = self._assess_overdraft_fees(account, day)
        accrual = self._accrue_interest(account, day)
        capitalized = ZERO
        if day == self._last_day and accrual.rounded_cumulative > 0:
            capitalized = accrual.rounded_cumulative
            self._system_post(account, INTEREST, capitalized, day, note="interest capitalization")
        self._closes.append(
            DayClose(
                seq=len(self._closes) + 1,
                account=account,
                day=day,
                closing_before_fees=closing_before_fees,
                closing=self.balance(account, day),
                available=self.available(account, day),
                fee_days=tuple(fee_days),
                accrued=accrual.amount,
                capitalized=to_money(capitalized, currency),
            )
        )

    def _assess_overdraft_fees(self, account, day):
        """Charge each day whose closing balance is negative, once (R1).

        Every day up to today is re-checked, so a backdated entry that turns
        an earlier day negative is charged when it becomes known. The fee is
        booked today with today's value date, whichever day it is for.
        """
        fee = self._overdraft_fee.get(self._accounts[account])
        charged = {p.for_day for p in self._postings if p.account == account and p.kind == FEE}
        fee_days = []
        for d in range(1, day + 1):
            if d in charged or self.balance(account, d) >= 0:
                continue
            if fee is None:
                message = f"Day {d} closed negative but no overdraft fee is defined for {self._accounts[account]}"
                if not any(n.account == account and n.message == message for n in self._notices):
                    self._system_notice(day, account, WARNING, "NO_FEE_CONFIGURED", message)
                continue
            self._system_post(account, FEE, -fee, day, for_day=d, note=f"overdraft fee for Day {d}")
            fee_days.append(d)
        return fee_days

    def _accrue_interest(self, account, day):
        """Accrue interest on positive closing balances (R2).

        Rounds the running total, not each day: today's accrual is the rounded
        cumulative figure minus what was accrued before. Nothing is lost or
        discarded, so the accruals sum exactly to the capitalized amount.
        """
        currency = self._accounts[account]
        daily = [max(self.balance(account, d), ZERO) * self._daily_rate for d in range(1, day + 1)]
        exact = sum(daily, ZERO)
        target = to_money(exact, currency)
        already = sum((a.amount for a in self._accruals if a.account == account), ZERO)
        accrual = Accrual(
            seq=len(self._accruals) + 1,
            account=account,
            day=day,
            amount=target - already,
            own_day_exact=daily[-1],
            exact_cumulative=exact,
            rounded_cumulative=target,
        )
        self._accruals.append(accrual)
        return accrual

    def _handlers(self):
        return {
            CREDIT: self._post_entry,
            DEBIT: self._post_entry,
            REVERSAL: self._reverse,
            AUTHORIZATION: self._authorize,
            SETTLEMENT: self._settle,
        }

    def _validate(self, event):
        if any(e.id == event.id for e in self._events):
            raise Rejected("DUPLICATE_EVENT", f"event id {event.id} was already applied")
        if event.account not in self._accounts:
            raise Rejected("UNKNOWN_ACCOUNT", f"unknown account {event.account!r}")
        for name, day in (("booked_day", event.booked_day), ("value_date", event.value_date)):
            if not isinstance(day, int) or not 1 <= day <= self._last_day:
                raise Rejected("DAY_OUT_OF_WINDOW", f"{name} {day!r} is outside Day 1-{self._last_day}")
        if self.closed_through(event.account) >= self._last_day:
            raise Rejected("WINDOW_CLOSED", f"{event.account} is closed through Day {self._last_day}")
        if event.currency is not None and event.currency != self._accounts[event.account]:
            raise Rejected(
                "CURRENCY_MISMATCH",
                f"{event.currency} event on {self._accounts[event.account]} account {event.account}",
            )

    def _amount(self, event):
        try:
            amount = parse_amount(event.amount, self._accounts[event.account])
        except MoneyError as e:
            raise Rejected("INVALID_AMOUNT", str(e)) from None
        if amount <= 0:
            raise Rejected("INVALID_AMOUNT", f"amount must be positive, got {amount}")
        return amount

    def _post_entry(self, event):
        amount = self._amount(event)
        currency = self._accounts[event.account]
        try:
            parts = split_evenly(amount, event.instalments, currency)
        except (MoneyError, TypeError):
            raise Rejected("INVALID_INSTALMENTS", f"bad instalment count {event.instalments!r}") from None
        sign = 1 if event.type == CREDIT else -1
        for i, part in enumerate(parts, start=1):
            note = f"instalment {i} of {len(parts)}" if len(parts) > 1 else ""
            self._post(event, event.type, sign * part, note=note)

    def _reverse(self, event):
        """Reverse a CREDIT or DEBIT by appending opposite postings.

        The original postings stay in the log untouched (R4).
        """
        originals = [
            p for p in self._postings
            if p.event_id == event.reverses and p.account == event.account and p.kind in (CREDIT, DEBIT)
        ]
        if not originals:
            raise Rejected(
                "REVERSAL_TARGET_NOT_FOUND",
                f"{event.reverses} is not a posted credit or debit on {event.account}",
            )
        if any(p.reverses == event.reverses for p in self._postings):
            raise Rejected("ALREADY_REVERSED", f"{event.reverses} was already reversed")
        total = sum((p.amount for p in originals), ZERO)
        if event.amount is not None and self._amount(event) != abs(total):
            raise Rejected(
                "REVERSAL_AMOUNT_MISMATCH",
                f"reversal amount {event.amount} does not match {event.reverses} ({abs(total)})",
            )
        for p in originals:
            self._post(event, REVERSAL, -p.amount, reverses=event.reverses, note=f"reverses {event.reverses}")

    def _authorize(self, event):
        """Approve only if available balance stays >= 0 after the hold (R5).

        A decline is a decision, not an error: it is recorded as an
        authorization state and the event is accepted into the log.
        """
        if not event.auth_id:
            raise Rejected("MISSING_AUTH_ID", "authorization has no auth_id")
        if event.auth_id in self.auth_states(event.account):
            raise Rejected("DUPLICATE_AUTHORIZATION", f"{event.auth_id} already exists")
        amount = self._amount(event)
        after = self.available(event.account, event.booked_day) - amount
        currency = self._accounts[event.account]
        if after >= 0:
            self._auth(event, APPROVED, hold=amount, reason=f"available after hold {fmt(after, currency)}")
        else:
            self._auth(event, DECLINED, hold=amount, reason=f"available after hold would be {fmt(after, currency)}")

    def _settle(self, event):
        """Post a settlement.

        A settlement reports money that has already moved at the scheme. The
        ledger records it even when no matching hold exists (a force-post),
        and flags it, because refusing would leave the ledger wrong about the
        account. Only a second settlement of the same authorization is refused.
        """
        if not event.auth_id:
            raise Rejected("MISSING_AUTH_ID", "settlement has no auth_id")
        amount = self._amount(event)
        currency = self._accounts[event.account]
        auth = self.auth_states(event.account).get(event.auth_id)
        if auth is None:
            self._post(event, FORCE_POST, -amount, note=f"{event.auth_id} unmatched")
            self._notice(
                event, WARNING, "UNMATCHED_SETTLEMENT",
                f"{event.auth_id} has no authorization; {fmt(amount, currency)} force-posted for dispute",
            )
        elif auth.state == SETTLED:
            raise Rejected("DUPLICATE_SETTLEMENT", f"{event.auth_id} was already settled by {auth.event_id}")
        elif auth.state == DECLINED:
            self._post(event, FORCE_POST, -amount, note=f"{event.auth_id} was declined")
            self._notice(
                event, WARNING, "SETTLEMENT_OF_DECLINED_AUTH",
                f"{event.auth_id} was declined; {fmt(amount, currency)} force-posted for dispute",
            )
        else:
            self._post(event, SETTLEMENT, -amount, note=f"settles {event.auth_id}")
            self._auth(event, SETTLED, hold=auth.hold, settled=amount, reason=f"hold {fmt(auth.hold, currency)} released")
            if amount > auth.hold:
                self._notice(
                    event, WARNING, "OVER_SETTLEMENT",
                    f"{event.auth_id} settled for {fmt(amount, currency)}, above its hold of {fmt(auth.hold, currency)}",
                )

    # ---- append helpers --------------------------------------------------

    def _auth(self, event, state, *, hold, settled=ZERO, reason=""):
        self._auths.append(
            AuthRecord(
                seq=len(self._auths) + 1,
                account=event.account,
                auth_id=event.auth_id,
                state=state,
                hold=hold,
                settled=settled,
                day=event.booked_day,
                event_id=event.id,
                reason=reason,
            )
        )

    def _post(self, event, kind, amount, *, value_date=None, for_day=None, reverses=None, note=""):
        posting = Posting(
            seq=len(self._postings) + 1,
            account=event.account,
            kind=kind,
            amount=amount,
            booked_day=event.booked_day,
            value_date=event.value_date if value_date is None else value_date,
            event_id=event.id,
            for_day=for_day,
            reverses=reverses,
            note=note,
        )
        self._postings.append(posting)
        return posting

    def _system_post(self, account, kind, amount, day, *, for_day=None, note=""):
        self._postings.append(
            Posting(
                seq=len(self._postings) + 1,
                account=account,
                kind=kind,
                amount=amount,
                booked_day=day,
                value_date=day,
                event_id=SYSTEM,
                for_day=for_day,
                note=note,
            )
        )

    def _system_notice(self, day, account, severity, code, message):
        self._notices.append(
            Notice(
                seq=len(self._notices) + 1, day=day, account=account, event_id=SYSTEM,
                severity=severity, code=code, message=message,
            )
        )

    def _notice(self, event, severity, code, message):
        self._notices.append(
            Notice(
                seq=len(self._notices) + 1,
                day=event.booked_day if isinstance(event.booked_day, int) else 0,
                account=event.account,
                event_id=event.id,
                severity=severity,
                code=code,
                message=message,
            )
        )
