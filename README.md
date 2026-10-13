# Account ledger core

An in-memory, append-only account ledger. Python 3 standard library only:
nothing to install. The task is in [BRIEF.md](BRIEF.md).

## Run it

Print the per-day report for the brief's event stream:

```bash
python3 -m ledger.replay
```

Run the test suite:

```bash
python3 -m unittest
```

**The suite is expected to end with `FAILED (failures=1)`.** The one failure
is `tests/test_known_gap.py`, a deliberate failing test against this design.
Its docstring explains what it reveals. Every other test passes. To run
everything except that test:

```bash
python3 -m unittest tests.test_money tests.test_postings tests.test_authorizations tests.test_day_close tests.test_scenario
```

## Reading the report

There is one block per day, with one section per account:

```
=== Day 5 ============================================================
ACC-001 (AED)
  events          E7 DEBIT 620.00 (value Day 2); E8 AUTHORIZATION Auth-B 90.00
  closing ledger  AED -410.00   (before fees AED -335.00)
  available       AED -410.00
  fees assessed   AED 25.00 for Day 2; AED 25.00 for Day 4; AED 25.00 for Day 5
  interest        accrued AED -0.46, running total AED 0.11
  authorizations  Auth-A SETTLED for AED 185.00 (...); Auth-B DECLINED AED 90.00 (...)
  errors          none
```

| Line | Meaning |
|---|---|
| events | Events booked on this day and accepted. "(value Day N)" marks a backdated entry. |
| closing ledger | The ledger balance when this day was closed, after that day's fees. "before fees" appears when fees changed it. On Day 6 it includes the capitalized interest. |
| available | Closing ledger balance minus active holds. |
| fees assessed | Overdraft fees booked at this close. "for Day N" is the negative day being charged, which can be earlier than the day of booking. |
| interest | The accrual booked at this close and the running total. An accrual can be negative when a backdated entry lowers earlier days. On Day 6 the running total is capitalized as one credit. |
| authorizations | Every authorization known by this day and its state: APPROVED (hold active), DECLINED, or SETTLED. |
| errors | `ERROR` means the event was refused and nothing was posted. `WARNING` means it was applied but flagged. |

After Day 6 a table compares each day's closing balance **as known at that
close** with the figure **restated** by value date at the end of the window.
They differ where a later backdated entry or its reversal changed the past.

## Layout

| Path | Contents |
|---|---|
| `ledger/money.py` | Currency precision, rounding, exact instalment split |
| `ledger/config.py` | Fee, interest rate, window length |
| `ledger/core.py` | The ledger: postings, authorizations, day close |
| `ledger/replay.py` | The brief's event stream and the report |
| `tests/` | Unit tests per module, `test_scenario.py` per criterion, `test_known_gap.py` (fails on purpose) |

## Documents

| File | Contents |
|---|---|
| [REJECTED.md](REJECTED.md) | The five criteria refused (C2, C4, C6, C7, C8) with reasons, and approaches abandoned |
| [AMBIGUITIES.md](AMBIGUITIES.md) | 36 ambiguities in the brief and how each was resolved |
| [NUMBERS.md](NUMBERS.md) | Every constant and why it has that value |
| [WORKLOG.md](WORKLOG.md) | What was done and when |

## How append-only is kept

Every record (event, posting, authorization step, accrual, day close, notice)
is a frozen dataclass in a list that is only ever appended to. Balances,
holds and authorization states are computed from those lists on demand and
never stored. A reversal, a fee and a settlement are each new records; the
records they relate to are left as they were.
