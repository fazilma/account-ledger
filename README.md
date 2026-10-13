# Account ledger core

An in-memory, append-only account ledger. Python 3 standard library only;
nothing to install. The task is in [BRIEF.md](BRIEF.md).

## Run

Print the per-day report:

```bash
python3 -m ledger.replay
```

Run the tests:

```bash
python3 -m unittest
```

The suite ends with `FAILED (failures=1)`. That one failure,
`tests/test_known_gap.py`, is deliberate. The other 59 tests pass.

## Reading the report

One block per day, one section per account.

| Line | Meaning |
|---|---|
| closing ledger | Balance when the day was closed, after that day's fees. On Day 6 it includes the interest paid in. |
| fees assessed | Fees booked at this close. "for Day N" is the negative day being charged. |
| authorizations | Each hold and its state: APPROVED, DECLINED or SETTLED. |
| errors | ERROR: event refused, nothing posted. WARNING: applied but flagged. |

## Files

| Path | Contents |
|---|---|
| `ledger/money.py` | Decimal places, rounding, exact splitting |
| `ledger/config.py` | Fee, interest rate, window length |
| `ledger/core.py` | The ledger: postings, holds, day close |
| `ledger/replay.py` | The event stream and the report |
| `tests/` | Tests per module, per criterion, and the deliberate failure |

## Documents

| File | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Architecture, trade-offs and production considerations |
| [REJECTED.md](REJECTED.md) | Criteria refused, and approaches dropped |
| [AMBIGUITIES.md](AMBIGUITIES.md) | What the brief left unclear and what was assumed |
| [NUMBERS.md](NUMBERS.md) | Every constant and why |
| [WORKLOG.md](WORKLOG.md) | Diary of the work |

## How it works

The ledger is a list of postings that is only ever added to. A balance is
the sum of an account's postings up to a value date; it is never stored.
Closing a day charges overdraft fees, counts interest and, on Day 6, pays
the interest in.
