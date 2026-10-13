"""Replay the brief's event stream and print the per-day report.

Run with:  python3 -m ledger.replay
"""

from .core import FEE, SETTLED, Event, Ledger
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


def replay(stream=STREAM, upto=None, **ledger_options):
    """Run the stream: for each day, apply that day's events, then close the day.

    Events keep their listed order within a day. `upto` stops straight after
    that event id, before its day is closed.
    """
    ledger = Ledger(ACCOUNTS, **ledger_options)
    for day in range(1, ledger.last_day + 1):
        for event in stream:
            if event.booked_day == day:
                ledger.apply(event)
                if event.id == upto:
                    return ledger
        ledger.close_day(day)
    return ledger


def _describe_auth(record, currency):
    if record.state == SETTLED:
        return f"{record.auth_id} SETTLED for {fmt(record.settled, currency)}"
    return f"{record.auth_id} {record.state} {fmt(record.hold, currency)}"


def _account_lines(ledger, close):
    account, day = close.account, close.day
    currency = ledger.accounts[account]
    fees = [p for p in ledger.postings if p.account == account and p.kind == FEE and p.booked_day == day]
    auths = ledger.auth_states(account, day).values()
    notices = [n for n in ledger.notices if n.account == account and n.day == day]

    closing = fmt(close.closing, currency)
    if close.capitalized:
        closing += f"   (includes capitalized interest {fmt(close.capitalized, currency)})"

    rows = [
        ("closing ledger", closing),
        ("fees assessed", "; ".join(f"{fmt(-p.amount, currency)} for Day {p.for_day}" for p in fees) or "none"),
        ("authorizations", "; ".join(_describe_auth(r, currency) for r in auths) or "none"),
        ("errors", "; ".join(f"{n.severity} {n.event_id} {n.code}: {n.message}" for n in notices) or "none"),
    ]
    return [f"{account} ({currency})"] + [f"  {label:<15} {text}" for label, text in rows]


def render(ledger):
    """Per day and per account: closing ledger balance, fees, authorization states, errors."""
    lines = []
    for day in range(1, ledger.last_day + 1):
        lines.append(f"=== Day {day} ===")
        for close in ledger.closes:
            if close.day == day:
                lines += _account_lines(ledger, close)
        lines.append("")
    return "\n".join(lines).rstrip()


def main():
    print(render(replay()))


if __name__ == "__main__":
    main()
