# Numbers

Every constant, whether the brief fixed it or we chose it, and why it is not
half that value.

## Fixed by the brief

| Constant | Value | Where | Why not half |
|---|---|---|---|
| Overdraft fee | AED 25.00 | `config.py` | Stated in R1. At 12.50 every figure from Day 5 on would differ from the brief. |
| Daily interest rate | 0.0004 | `config.py` | R2 says 0.04%, which is 0.0004 as a multiplier. Half would halve all interest. |
| AED decimals | 2 | `money.py` | R3. One decimal cannot hold amounts like 0.26. |
| BHD decimals | 3 | `money.py` | R3. Fewer cannot hold 3.333. |
| Window | 6 days | `config.py` | The brief runs Day 1 to Day 6. At 3, half the events fall outside. |
| Hold approved when | available is 0 or more | `core.py` `_authorize` | R5: "at or above zero". |
| Fee charged when | closing balance is below 0 | `core.py` `_charge_overdraft_fees` | R1: "negative". Zero is not negative. |
| Interest earned when | balance is above 0 | `core.py` `_accrue_interest` | R2: "positive balances only". |
| Event amounts and days | as listed | `replay.py` | Copied from the brief. |

## Chosen by us

| Constant | Value | Where | Why |
|---|---|---|---|
| Rounding mode | half-even | `money.py` | The brief says "rounded" with no mode. Half-even does not lean up or down over many days. No figure in this stream lands on a tie, so the output is the same under half-up. |
| What is rounded | the running interest total | `core.py` `_accrue_interest` | Rounding each day separately loses fractions. Rounding the total loses nothing, which R2 requires. |
| Spare unit in a split | goes to the first instalment | `money.py` `split_evenly` | 10.000 / 3 leaves 0.001. It cannot be halved; 0.0005 does not exist in BHD. |
| Working precision | 28 digits | Python's `decimal` default | Enough to hold balance x 0.0004 exactly. At 14 digits, large balances would lose digits silently. |

## Test-only

| Constant | Value | Why |
|---|---|---|
| Sweep step | 7919 | A prime, so tested amounts share no pattern with the rate. |
| Split sweep | 0 to 499 in steps of 7, into 1, 2, 3 and 7 parts | Hits every remainder for each divisor. |
