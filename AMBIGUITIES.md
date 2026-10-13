# Ambiguities

What the brief leaves unclear, and what was assumed. Rule and criterion
numbers refer to BRIEF.md.

## Overdraft fees

| # | Unclear | Assumed |
|---|---|---|
| A1 | Is a backdated overdraft charged? | Yes. Every close re-checks all earlier days and charges any day that has turned negative. |
| A2 | Does "once per day" mean one fee per negative day, or one fee per calendar day? | One per negative day. Three fees can be booked on the same day. |
| A3 | What value date does a late fee carry? | The day it is charged, as R1 says. Not the day it is for. |
| A4 | Do fees booked today count in today's closing balance? | Yes. R1 says "all entries". A fee can therefore push a day negative. |
| A5 | Is a fee refunded when its cause is reversed? | No. The brief gives no refund rule, and the fee was correct when charged. This leaves a known gap; see the failing test. |
| A6 | Is a zero balance charged? | No. Only below zero. |
| A7 | What is the fee for BHD? | None is defined, so none is charged. |
| A8 | Can a plain debit overdraw the account? | Yes. R5 limits holds only. |

## Interest

| # | Unclear | Assumed |
|---|---|---|
| A9 | Is past interest corrected after a backdated entry? | Yes. Interest is only a running tally until Day 6, so correcting it changes nothing already posted. A fee is already posted, which is why A5 differs. |
| A10 | Can a day's interest be negative? | Yes, as a correction under A9. The running total never goes below zero. |
| A11 | How do daily amounts sum exactly to the total? | The running total is rounded, and each day records the change in it. |
| A12 | Does Day 6 earn interest before the pay-in? | Yes. |
| A13 | Is interest worked out before or after that day's fees? | After. |
| A14 | Does interest apply to the BHD account? | Yes. R2 names no currency. |
| A15 | Simple or compound? | Simple. Interest is not in the balance until Day 6. |
| A16 | Which rounding mode? | Half-even. It makes no difference to this stream. |

## Holds and settlements

| # | Unclear | Assumed |
|---|---|---|
| A17 | Which balance does a hold test? | Ledger balance on the booking day, minus active holds, minus the new hold. Zero is approved. |
| A18 | Auth-A settles for 185 against a 200 hold. What about the 15? | The whole hold is released. |
| A19 | A settlement above its hold? | Posted like any other. |
| A20 | A settlement with no hold (E6)? | Posted and flagged. See REJECTED.md, C4. |
| A21 | A settlement against a declined hold? | Same as A20. |
| A22 | A second settlement of the same hold? | Same as A20. The ledger cannot tell a duplicate from a genuine second claim. |
| A23 | Is a decline an error? | No. It is a state. |
| A24 | Is Auth-B reconsidered after E9? | No. The answer was already given. |
| A25 | Do holds expire? | No. The brief gives no period. |
| A26 | Are hold IDs unique per account or overall? | Per account. |

## Events and dates

| # | Unclear | Assumed |
|---|---|---|
| A27 | E9 (Day 6) is listed before E10 (Day 5). | Events are applied day by day, in listed order within a day. E9 and E10 are on different accounts, so the result is the same. |
| A28 | An event for a day already closed? | Not checked. The day-by-day replay cannot produce one. |
| A29 | What does E9's value date of Day 2 mean? | The cancelling entry counts from Day 2. Both entries stay in the ledger. |
| A30 | What can be reversed? | Only a credit or debit, and only once. |
| A31 | Can a value date be after the booking day? | Yes. The entry counts from its value date. |
| A32 | "Three equal instalments" of 10.000? | Not possible at 3 decimals. 3.334, 3.333, 3.333. |
| A33 | An input with too many decimals? | Refused, not rounded. |

## Reporting

| # | Unclear | Assumed |
|---|---|---|
| A34 | Which closing balance is printed? | The one known when the day closed. A table at the end shows the corrected figures. |
| A35 | Does the Day 6 balance include interest? | Yes. |
| A36 | What is an "error"? | Refusals and warnings both appear, each labelled. |

## Not handled

Left out on purpose, because the stream does not need them:

- duplicate event IDs
- dates outside Day 1 to Day 6
- a second hold reusing a hold ID
- a reversal whose stated amount differs from the original
