# Brief (restructured from the original task text)

## What to build

An in-memory account ledger core. No web layer, persistence, UI or database.
A runnable suite or script replays the event stream and prints, per day:
closing ledger balance, fee assessments, authorization states, and errors.
The window is Day 1 to Day 6.

## Accounts

| Account | Currency | Decimals | Opening balance |
|---|---|---|---|
| ACC-001 | AED | 2 | 0.00 |
| ACC-002 | BHD | 3 | 0.000 |

## Rules

| # | Rule |
|---|---|
| R1 | Overdraft fee AED 25.00, once per day per account, when that day's closing ledger balance (all entries with value_date <= that day) is negative. Booked with value_date equal to the day assessed. |
| R2 | Daily interest 0.04% on the closing ledger balance, positive balances only. Accruals capitalize as a single credit at end of Day 6. Rounded daily accruals must sum exactly to the capitalized total. |
| R3 | AED is 2 decimal places, BHD is 3. Amounts stored and rounded to their own precision. |
| R4 | The ledger is append-only. No event record is ever mutated or deleted. |
| R5 | An authorization is approved only if available balance (ledger balance minus active holds) stays at or above zero after the hold is applied. |

## Event stream (replayed in this order)

| # | Booked | Type | Account | Details | Value date |
|---|---|---|---|---|---|
| E1 | Day 1 | CREDIT | ACC-001 | AED 1,200.00 | Day 1 |
| E2 | Day 1 | DEBIT | ACC-001 | AED 950.00 | Day 1 |
| E3 | Day 2 | AUTHORIZATION | ACC-001 | Auth-A hold AED 200.00 | Day 2 |
| E4 | Day 3 | CREDIT | ACC-001 | AED 400.00 | Day 3 |
| E5 | Day 4 | SETTLEMENT | ACC-001 | Auth-A settles for AED 185.00 | Day 4 |
| E6 | Day 4 | SETTLEMENT | ACC-001 | Auth-Z settles for AED 180.00 (no preceding authorization) | Day 4 |
| E7 | Day 5 | DEBIT | ACC-001 | AED 620.00 | Day 2 |
| E8 | Day 5 | AUTHORIZATION | ACC-001 | Auth-B hold AED 90.00 | Day 5 |
| E9 | Day 6 | REVERSAL | ACC-001 | Reverses E7 | Day 2 |
| E10 | Day 5 | CREDIT | ACC-002 | BHD 10.000 as three equal instalments | Day 5 |

Auth-B is never settled inside the window.

## Acceptance criteria (some are wrong; see REJECTED.md)

| # | Criterion |
|---|---|
| C1 | The Day 2 closing ledger balance, evaluated at end of Day 5 and before any fee is assessed, is AED -370.00. |
| C2 | E7 causes exactly one overdraft fee to be assessed, on Day 2. |
| C3 | The Day 4 settlement of Auth-A must be accepted. |
| C4 | Any settlement referencing an authorization ID not present in the ledger must be rejected and the funds must not leave the account. |
| C5 | If Auth-B is approved, its hold reduces available balance but not ledger balance. |
| C6 | After E9, all balances and fees return to their pre-E7 values. |
| C7 | The three BHD instalments in E10 must each be BHD 3.334. |
| C8 | If the rounded daily interest accruals do not sum to the capitalized total, the remainder is discarded. |

## Deliverables

Intact commit history, plus README, NUMBERS.md, AMBIGUITIES.md, REJECTED.md,
WORKLOG.md, and one failing test against our own design, annotated inline.
