"""Replay the brief's event stream and print the per-day report.

Run with:  python3 -m ledger.replay
"""

from .core import ERROR, FEE, SETTLED, Event, Ledger
from .money import fmt

ACCOUNTS = {"ACC-001": "AED", "ACC-002": "BHD"}

# The stream from the brief, in the order given (E9 before E10).
STREAM = (
    Event("E1", 1, "CREDIT", "ACC-001", "AED", "1200.00", value_date=1),
    Event("E2", 1, "DEBIT", "ACC-001", "AED", "950.00", value_date=1),
    Event("E3", 2, "AUTHORIZATION", "ACC-001", "AED", "200.00", value_date=2, auth_id="Auth-A"),
    Event("E4", 3, "CREDIT", "ACC-001", "AED", "400.00", value_date=3),
    Event("E5", 4, "SETTLEMENT", "ACC-001", "AED", "185.00", value_date=4, auth_id="Auth-A"),
    Event("E6", 4, "SETTLEMENT", "ACC-001", "AED", "180.00", value_date=4, auth_id="Auth-Z"),
    Event("E7", 5, "DEBIT", "ACC-001", "AED", "620.00", value_date=2),
    Event("E8", 5, "AUTHORIZATION", "ACC-001", "AED", "90.00", value_date=5, auth_id="Auth-B"),
    Event("E9", 6, "REVERSAL", "ACC-001", "AED", value_date=2, reverses="E7"),
    Event("E10", 5, "CREDIT", "ACC-002", "BHD", "10.000", value_date=5, instalments=3),
)


def replay(stream=STREAM, upto=None):
    """Apply the stream in order. `upto` stops after that event id, without closing."""
    ledger = Ledger(ACCOUNTS)
    for event in stream:
        ledger.apply(event)
        if event.id == upto:
            return ledger
    ledger.finish()
    return ledger


def _describe_event(event):
    parts = [event.id, event.type]
    if event.auth_id:
        parts.append(event.auth_id)
    if event.reverses:
        parts.append(f"of {event.reverses}")
    if event.amount is not None:
        parts.append(str(event.amount))
    if event.instalments > 1:
        parts.append(f"in {event.instalments} instalments")
    if event.value_date != event.booked_day:
        parts.append(f"(value Day {event.value_date})")
    return " ".join(parts)


def _describe_auth(record, currency):
    if record.state == SETTLED:
        return f"{record.auth_id} SETTLED for {fmt(record.settled, currency)} ({record.reason})"
    return f"{record.auth_id} {record.state} {fmt(record.hold, currency)} ({record.reason})"


def _account_lines(ledger, account, day):
    currency = ledger.currency(account)
    close = next(c for c in ledger.closes if c.account == account and c.day == day)
    accrual = next(a for a in ledger.accruals if a.account == account and a.day == day)
    events = [e for e in ledger.events if e.account == account and e.booked_day == day]
    fees = [p for p in ledger.postings if p.account == account and p.kind == FEE and p.booked_day == day]
    auths = ledger.auth_states(account, day).values()
    notices = [n for n in ledger.notices if n.account == account and n.day == day]

    closing = fmt(close.closing, currency)
    if close.closing_before_fees != close.closing:
        details = [f"before fees {fmt(close.closing_before_fees, currency)}"]
        if close.capitalized:
            details = [f"includes capitalized interest {fmt(close.capitalized, currency)}"]
        closing += f"   ({', '.join(details)})"
    interest = f"accrued {fmt(accrual.amount, currency)}, running total {fmt(accrual.rounded_cumulative, currency)}"
    if close.capitalized:
        interest += f", capitalized {fmt(close.capitalized, currency)}"

    rows = [
        ("events", "; ".join(_describe_event(e) for e in events) or "none"),
        ("closing ledger", closing),
        ("available", fmt(close.available, currency)),
        ("fees assessed", "; ".join(f"{fmt(-p.amount, currency)} for Day {p.for_day}" for p in fees) or "none"),
        ("interest", interest),
        ("authorizations", "; ".join(_describe_auth(r, currency) for r in auths) or "none"),
        ("errors", "; ".join(f"{n.severity} {n.event_id} {n.code}: {n.message}" for n in notices) or "none"),
    ]
    return [f"{account} ({currency})"] + [f"  {label:<15} {text}" for label, text in rows]


def render(ledger):
    lines = []
    for day in range(1, ledger.last_day + 1):
        lines += [f"=== Day {day} " + "=" * 60]
        for account in ledger.accounts:
            lines += _account_lines(ledger, account, day)
        lines.append("")

    lines += ["=== Closing ledger balance: as known at each close vs restated at end of window ==="]
    for account, currency in ledger.accounts.items():
        lines.append(f"{account} ({currency})")
        for close in (c for c in ledger.closes if c.account == account):
            restated = ledger.balance(account, close.day)
            mark = "" if restated == close.closing else "   <- restated by later backdated entries"
            lines.append(
                f"  Day {close.day}   at close {fmt(close.closing, currency):>14}"
                f"   restated {fmt(restated, currency):>14}{mark}"
            )
    errors = sum(1 for n in ledger.notices if n.severity == ERROR)
    lines += ["", f"Events applied: {len(ledger.events)}. Refused: {errors}. Warnings: {len(ledger.notices) - errors}."]
    return "\n".join(lines)


def main():
    print(render(replay()))


if __name__ == "__main__":
    main()
