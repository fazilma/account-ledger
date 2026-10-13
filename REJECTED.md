# Rejected

Rule and criterion numbers (R1-R5, C1-C8) refer to BRIEF.md.

## Part 1: acceptance criteria refused

Five of the eight criteria are refused. Each has a test in
`tests/test_scenario.py` (`RefusedCriteriaTest`) asserting what the ledger
does instead.

### C2: "E7 causes exactly one overdraft fee to be assessed, on Day 2." Refused.

Two things are wrong.

**The count.** E7 is a debit of 620.00 value-dated Day 2. With it, the closing
balances by value date are:

| Day | Without E7 | With E7 | Negative? |
|---|---|---|---|
| 1 | 250.00 | 250.00 | no |
| 2 | 250.00 | -370.00 | yes |
| 3 | 650.00 | 30.00 | no (E4 credit of 400.00) |
| 4 | 285.00 | -335.00 | yes (E5 and E6 settlements) |
| 5 | 285.00 | -335.00 | yes |

R1 charges every day whose closing balance is negative. That is three days,
so three fees, AED 75.00. Without E7 there are none, so all three are caused
by E7. (If C4 had been accepted and E6 not posted, Days 4 and 5 would be
-155.00: still negative, still three fees.)

**The day.** E7 is booked on Day 5. Nothing can be assessed on Day 2 because
on Day 2 the ledger did not know about E7. R1 says the fee is "booked with
value_date equal to the day assessed", so all three carry value date Day 5.
Booking a fee with value date Day 2 would contradict R1 and would also
change Day 3's balance after the fact.

What the ledger does: three fees at the Day 5 close, for Days 2, 4 and 5, all
value-dated Day 5.

### C4: "Any settlement referencing an authorization ID not present in the ledger must be rejected and the funds must not leave the account." Refused.

This is the most debatable refusal, and no rule in the brief contradicts C4
directly. The reasoning is about what a settlement is.

An authorization is a question ("may this be spent?") and the ledger can say
no. A settlement is a report: the scheme has already moved the money to the
merchant. Refusing to record it does not bring the money back. It only makes
the ledger disagree with the bank's real position, and shows the customer
180.00 that the bank no longer has. Settlements without a matching
authorization are also ordinary: offline terminals, authorizations that aged
out, and IDs mangled in transit all produce them.

The correct control is to post and dispute, not to refuse and ignore. The
ledger therefore posts E6 as a `FORCE_POST` debit of 180.00 and raises the
warning `UNMATCHED_SETTLEMENT`, which appears in the Day 4 errors line.

"The funds must not leave the account" is also not something this ledger
could deliver: the funds left before the event arrived.

If a reviewer holds that C4 is correct as written, the change is confined to
`Ledger._settle` in `ledger/core.py`: raise `Rejected` in the `else` branch
instead of posting. Days 4 and 5 would then close at 465.00 and -155.00
before fees.

### C6: "After E9, all balances and fees return to their pre-E7 values." Refused.

E9 restores the 620.00 principal on value date Day 2. It cannot restore
"all" of the rest:

- **Fees.** The three fees booked on Day 5 are entries in an append-only
  ledger (R4). They can only be offset by new entries, and no rule in the
  brief says a reversal waives fees. The ledger leaves them in place. This is
  the design's weakest point and is the subject of the deliberately failing
  test, `tests/test_known_gap.py`.
- **Auth-B.** It was declined on Day 5 because of E7. The merchant was told
  no. A reversal on Day 6 cannot un-decline it.
- **Interest.** The fees lower the Day 5 and Day 6 balances, so the account
  capitalizes 0.74 instead of 0.80.
- **The log.** E7 and E9 are both permanently in it.

Day 6 closes at AED 210.74. Had E7 never been booked it would be 285.80.

### C7: "The three BHD instalments in E10 must each be BHD 3.334." Refused.

3 x 3.334 = 10.002. E10 is a credit of 10.000, so this creates 0.002 from
nothing. Three equal instalments of 10.000 do not exist at 3 decimal places
(R3). The ledger posts 3.334 + 3.333 + 3.333 = 10.000.

### C8: "If the rounded daily interest accruals do not sum to the capitalized total, the remainder is discarded." Refused.

It contradicts R2, which is listed as non-negotiable: "The rounded daily
accruals must sum exactly to the capitalized total." If they must sum
exactly, there is no remainder to discard. The ledger rounds the running
total and books each day's accrual as the difference from what was accrued
before, so the sum is exact by construction (see `Ledger._accrue_interest`).

## Criteria accepted

| # | Result |
|---|---|
| C1 | True. 250.00 - 620.00 = -370.00. |
| C3 | True. 185.00 against a 200.00 hold; the whole hold is released. |
| C5 | True as a conditional, and tested on a variant stream. In the actual stream Auth-B is **declined**: at E8 the ledger balance is already -335.00, so available after the hold would be -425.00. |

## Part 2: approaches abandoned

These were dropped while designing or building. Where it happened is stated.

| Approach | When | Why it was dropped |
|---|---|---|
| Close a day for all accounts as soon as the stream moves to a later booking day | Design, before coding | E10 is booked Day 5 but listed after E9 (Day 6). A global close would have closed Day 5 for ACC-002 before its only event arrived. Replaced by per-account lazy closing: applying an event closes that account's earlier days. |
| Keep a separate "carried remainder" field per account plus separate adjustment entries for backdated changes | Design, before coding | Two mechanisms for one problem, and a mutable field. Replaced by one rule: accrual = rounded cumulative interest as now known, minus everything accrued so far. |
| Value-date a retroactive fee on the day it is *for* (Day 2) | Design, before coding | Contradicts R1 and would let a fee change earlier days' balances, cascading into more fees. |
| Mark the known-gap test with `unittest.expectedFailure` | Design, before coding | The suite would then report success. The brief asks for a failing test, so it fails for real. |
| Start balance sums from a bare `Decimal(0)` | Build, found by a failing test | An account with no postings reported `0` instead of `0.000`. Sums now start from zero at the currency's precision. |
| Compare whole `DayClose` records to prove stream order does not matter | Build, found by a failing test | The records carried a global sequence number that depended on account interleaving. Sequence numbers were later removed altogether. |
| Per-account lazy closing (applying an event closes that account's earlier days) | Build, after review | It honoured the listed order literally but hid the day loop inside `apply`. Replaced by an explicit loop in the replay: apply the day's events, close the day. |
| Handling for cases the stream never contains: over-settlement, declined-authorization and duplicate settlements as separate paths, late bookings, closed-window checks, duplicate IDs, a no-fee warning | Build, after review | The first version had 22 error and warning paths, of which the brief's stream reaches one. It made a simple ledger hard to read. `core.py` went from 524 to 327 lines; the cases are now listed as not handled in AMBIGUITIES.md. |
| Separate `Accrual` record and log | Build, after review | One accrual is made per account per close, so it is now two fields on `DayClose`. |
