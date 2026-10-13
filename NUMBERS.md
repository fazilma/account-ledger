# Numbers

Every constant in the code, where it lives, whether the brief fixed it or it
was chosen here, and why it is that value and not half of it.

## Fixed by the brief

| Constant | Value | Where | Why this value, and not half |
|---|---|---|---|
| Overdraft fee (AED) | 25.00 | `config.OVERDRAFT_FEE` | Stated in R1. At 12.50 the Day 5 close would be -372.50 instead of -410.00 and Day 6 would capitalize a different interest figure; every number after Day 4 would disagree with the brief. |
| Daily interest rate | 0.0004 | `config.DAILY_INTEREST_RATE` | R2 says 0.04% per day. 0.04% is 0.0004 as a multiplier, not 0.04 and not 0.004; it is written as a string-built Decimal so it is exact. At half (0.02%), ACC-002 would accrue 0.002 a day and ACC-001 would capitalize 0.37. |
| AED precision | 2 decimal places | `money.PRECISION` | R3, and the dirham's minor unit (fils) is 1/100. At 1 decimal place the 950.00 and 185.00 would survive but interest accruals such as 0.26 and 0.11 could not be represented. |
| BHD precision | 3 decimal places | `money.PRECISION` | R3, and the Bahraini dinar's minor unit (fils) is 1/1000. Anything less cannot represent E10's instalments of 3.333. |
| Window length | 6 days | `config.WINDOW_DAYS` | The brief's window is Day 1 to Day 6 and interest capitalizes at the end of Day 6. At 3, E5 to E10 would be refused as outside the window. |
| Approval threshold | available >= 0 | `Ledger._authorize` | R5: "remains at or above zero". Zero is approved; one minor unit below is declined. Both sides are tested. |
| Overdraft threshold | closing < 0 | `Ledger._charge_overdraft_fees` | R1: "is negative". Zero is not negative, so a zero close is free. |
| Interest floor | balance > 0 only | `Ledger._accrue_interest` (`max(balance, 0)`) | R2: "positive balances only". No debit interest is charged on overdrawn days; the overdraft fee is the only cost. |
| Instalment count for E10 | 3 | `replay.STREAM` | Stated in E10. |
| All event amounts and days | as listed | `replay.STREAM` | Copied from the brief's event stream, entered as strings so no float is ever involved. |

## Chosen here

| Constant | Value | Where | Why this value, and not half |
|---|---|---|---|
| Rounding mode | half-even | `money.ROUNDING` | The brief says "rounded" without a mode. Half-even has no upward bias over many accruals, which is why it is the usual choice for interest. Half-up would favour the customer on every tie. No amount in this stream lands exactly on a tie, so the output is the same under either; the choice matters only for other inputs. There is no "half" of a rounding mode; the real alternative is half-up, and it was not chosen for the bias reason. |
| What gets rounded | the running interest total | `Ledger._accrue_interest` | Rounding each day separately loses up to half a minor unit per day (0.024 over six days on a 285.00 balance; see `test_remainder_is_carried_not_discarded`). Rounding the total once loses nothing and satisfies R2. |
| Instalment remainder | 1 minor unit each to the first instalments | `money.split_evenly` | 10.000 / 3 leaves 0.001 over. It has to go somewhere and one whole minor unit is the smallest amount that exists; half a unit (0.0005) is not representable in BHD. "First" rather than "last" is a convention: the earliest instalment is the one already due. |
| Decimal working precision | 28 significant digits | Python's default `decimal` context, left unchanged | The only inexact-looking step is balance x 0.0004, which adds 4 decimal places; cumulative interest therefore needs the balance's digits plus 4. At 28 digits that is exact for balances up to about 10^21. At half (14 digits) an AED balance above 99,999,999.99 would silently lose digits in the interest sum. |
| Fee value date | the day assessed | `Ledger._charge_overdraft_fees` | Follows R1's wording. See AMBIGUITIES.md A3. |
| Opening balances | 0.00 and 0.000 | `Ledger.balance` | Stated in the brief. Implemented as "no postings", with sums starting from zero at the currency's precision, so no opening entry is invented. |

## Test-only numbers

| Constant | Value | Where | Why |
|---|---|---|---|
| Sweep step | 7919 minor units, up to 200000 | `test_accruals_always_sum_to_the_capitalized_total` | A prime step, so the amounts tested do not share a pattern with the 0.0004 rate. 26 amounts per currency keeps the suite under a tenth of a second; halving the step doubles the cases without covering a new kind of input. |
| Split sweep | 0 to 499 cents in steps of 7; parts 1, 2, 3, 7 | `test_split_always_sums_to_total` | Covers every remainder for each divisor more than once. |
| Counterfactual figures | 285.80, 0.80 | `test_c6_...` | Not constants of the design: what the stream yields with E7 and E9 removed, computed by the ledger and checked by hand (0.10 + 0.10 + 0.26 + 3 x 0.114 = 0.802). |

## Cosmetic

The report's label column is 15 characters wide and the day rule is 60
characters. They affect nothing but alignment.
