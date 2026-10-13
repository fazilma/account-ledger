# Rejected

Rule and criterion numbers refer to BRIEF.md.

## Criteria refused

| # | Criterion | Why it is wrong | What the ledger does |
|---|---|---|---|
| C2 | E7 causes exactly one fee, on Day 2. | E7 makes Days 2, 4 and 5 negative, so three fees. They are charged on Day 5, when E7 arrives; R1 dates a fee on the day it is charged. | Three fees at the Day 5 close. |
| C4 | A settlement with an unknown hold ID must be rejected and the funds must not leave. | A settlement reports money that has already moved. Refusing it makes the ledger wrong about the account. | Posts it and raises a warning. |
| C6 | After E9, all balances and fees return to pre-E7 values. | E9 restores the 620.00 only. The fees stay, Auth-B stays declined, interest is lower, and no record is erased (R4). | Day 6 closes at 210.74. |
| C7 | Each BHD instalment is 3.334. | 3 x 3.334 = 10.002, more than the 10.000 received. | 3.334 + 3.333 + 3.333. |
| C8 | An interest remainder is discarded. | R2 says the daily amounts must sum exactly to the total. | Rounds the running total; nothing is lost. |

C4 is the most debatable: no rule in the brief contradicts it. To follow C4
instead, refuse the event in the `else` branch of `Ledger._settle`.

## Criteria accepted

| # | Result |
|---|---|
| C1 | True. 250.00 - 620.00 = -370.00. |
| C3 | True. 185.00 against a 200.00 hold. |
| C5 | True as stated, but Auth-B is declined: the balance is already -335.00. |

## Approaches dropped

| Approach | Why |
|---|---|
| Closing days as the stream moves forward | E10 (Day 5) is listed after E9 (Day 6), so Day 5 would close before E10 arrived. |
| Dating a late fee on the day it is for | Contradicts R1 and would change earlier balances. |
| A stored remainder for interest rounding | Rounding the running total does the same with nothing to store. |
| Marking the failing test as an expected failure | The suite would report success. The brief asks for a failing test. |
| Each account closing its own earlier days when an event arrives | It worked but hid the day loop. Replaced by an explicit loop. |
| Handling many cases the stream never contains | The first version had 22 error and warning paths; the stream reaches one. Cut to keep the ledger readable. |
| A separate interest record | One is made per close, so it became two fields on the day-close record. |
