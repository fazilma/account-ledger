# Ambiguities

Each entry: what the brief leaves open, what was chosen, and what the other
reading would change. Rule and criterion numbers refer to BRIEF.md.

## Overdraft fees (R1)

**A1. When is a backdated overdraft charged?**
E7 is booked Day 5 with value date Day 2. R1 says "assessed once per day ...
when that day's closing ledger balance is negative" but not whether earlier
days are re-examined.
*Chosen:* every day close re-checks all days up to today and charges any
newly negative day once. C1 and C2 both presuppose that Day 2 is revisited.
*Other reading:* only today is checked. E7 would then cost one fee (Day 5).

**A2. What does "once per day" limit?**
It could mean one fee per negative day, or at most one fee booked on any
calendar day.
*Chosen:* one fee per negative day. Three fees are booked on Day 5, for Days
2, 4 and 5.
*Other reading:* a single fee on Day 5; Days 2 and 4 would never be charged.

**A3. What value date does a retroactive fee carry?**
*Chosen:* the day it is assessed (Day 5), following R1's wording literally.
*Other reading:* the day it is for. Rejected because fees would then change
earlier days' balances and trigger further fees.

**A4. Do fees booked today count in today's closing balance?**
R1 says "all entries". Retroactive fees booked on Day D have value date D.
*Chosen:* yes, literally. A day that is positive before retroactive fees can
be pushed negative by them and is then charged as well. It does not occur in
the brief's stream (Day 5 is already negative) and is pinned by
`test_fees_booked_today_count_in_todays_closing_balance`.
*Other reading:* test the balance before any of today's fees.

**A5. Is a fee refunded when the entry that caused it is reversed?**
*Chosen:* no. See REJECTED.md (C6) and the failing test.

**A6. Does a zero closing balance attract a fee?**
*Chosen:* no. "Negative" means below zero.

**A7. What is the overdraft fee for BHD?**
R1 gives AED 25.00 only. ACC-002 never goes negative, so the stream does not
need an answer.
*Chosen:* no fee is configured for BHD, and a negative BHD day is charged
nothing. Converting AED 25.00 at an invented rate would be worse than not
charging. *Not handled:* the ledger does not warn when this happens.

**A8. Can a plain debit overdraw the account?**
R5 limits authorizations only.
*Chosen:* yes. E7 must post for C1 to hold, and R1 would be pointless if
overdrafts could not happen.

## Interest (R2)

**A9. Is interest for earlier days restated after a backdated entry?**
*Chosen:* yes. Each close computes interest for all days as now known and
books the difference. On Day 5 that is -0.46: the 0.57 accrued through Day 4
shrinks to 0.11 once E7 is known. On Day 6 it is +0.63 after E9.
*Other reading:* accruals are final once made. The account would capitalize
0.57 plus Day 6, having earned interest on days it was overdrawn.
*Why restate interest but not refund fees?* Interest is a pure function of
the balance. A fee is a charge for an event, and waiving it is a decision.

**A10. Can a daily accrual be negative?**
A consequence of A9. *Chosen:* yes, as a restatement. The running total
never goes below zero.

**A11. How is the "sum exactly" requirement met?**
*Chosen:* round the running total, not each day. Daily accrual = rounded
cumulative minus previously accrued.
*Other reading:* round each day and add a final correcting entry on Day 6.
Equivalent total, but the last day would carry an unexplained lump.

**A12. Does Day 6 itself earn interest before capitalization?**
"At end of Day 6" does not say whether Day 6's accrual is in the total.
*Chosen:* yes. Order at the Day 6 close: fees, Day 6 accrual, capitalize.

**A13. Does interest for a day use the balance before or after that day's fees?**
*Chosen:* after. Fees are value-dated that day, so they are part of the
closing balance.

**A14. Is the rate applied to the BHD account too?**
R2 names no currency. *Chosen:* yes, both accounts.

**A15. Simple or compound within the window?**
*Chosen:* simple. Accruals are not part of the ledger balance until
capitalized at the end of Day 6, so they earn nothing before then.

**A16. Rounding mode.**
R3 says "rounded" without a mode. *Chosen:* half-even. No figure in this
stream lands on a tie, so the choice does not affect the output.

## Authorizations and settlements (R5)

**A17. Which balance does an authorization test?**
*Chosen:* the ledger balance by value date as of the authorization's booking
day, minus active holds, minus the new hold. Approved at exactly zero.

**A18. Auth-A settles for 185.00 against a 200.00 hold. What happens to the 15.00?**
*Chosen:* the whole hold is released at settlement.
*Other reading:* 15.00 stays held until an expiry the brief does not define.

**A19. A settlement above its hold.**
Not in the stream. *Chosen:* post the settled amount and release the hold,
the same as any settlement. *Not handled:* no warning is raised.

**A20. A settlement with no authorization (E6).**
*Chosen:* force-post and warn. See REJECTED.md (C4).

**A21. A settlement against a declined authorization.**
Not in the stream. *Chosen:* same as A20. The rule is one line: a settlement
with no active hold is force-posted and flagged `UNMATCHED_SETTLEMENT`.

**A22. A second settlement of the same authorization.**
Not in the stream. *Chosen:* same rule as A21: the hold is gone, so it is
force-posted and flagged. *Not handled:* the ledger does not tell a true
duplicate apart from a second genuine presentment; both go to dispute.

**A23. Is a declined authorization an error?**
The brief asks for "authorization states" and "errors" separately.
*Chosen:* a decline is a state, not an error. Auth-B shows as DECLINED and
the Day 5 errors line stays empty.

**A24. Is Auth-B re-decided after E9 restores the balance?**
*Chosen:* no. The decision was communicated on Day 5.

**A25. Do holds expire?**
"Auth-B is never settled inside the window" hints at it, but no period is
given. *Chosen:* no expiry. It is moot here because Auth-B is declined and
never holds anything.

**A26. Are authorization IDs unique per account or globally?**
*Chosen:* per account. A settlement on one account never matches a hold on
another.

## Events, dates and order

**A27. E9 (Day 6) is listed before E10 (Day 5).**
"Replayed in this order" conflicts with day order.
*Chosen:* the replay works day by day: apply that day's events in their
listed order, then close the day. So E10 is applied on Day 5 and E9 on Day
6. The listed order is kept wherever it can matter: within a day, and for
any two events on the same account. E9 and E10 are on different accounts,
and `test_listing_e10_after_e9_changes_nothing` confirms the result is the
same either way.
*Other reading:* apply strictly in listed order and close days as the
stream advances. Day 5 would then close for ACC-002 before E10 arrived.

**A28. An event booked on a day already closed for its account.**
Not in the stream, and the day-by-day replay cannot produce it.
*Not handled:* the ledger does not check. If a caller did apply such an
event, the next close would pick it up, because every close re-checks all
earlier days for fees and restates interest; but nothing would flag it, and
after the Day 6 close nothing would pick it up at all.

**A29. What does the reversal's value date mean?**
E9 is booked Day 6 with value date Day 2.
*Chosen:* the compensating entry takes value date Day 2, so Day 2 onward is
restated as if E7 had not applied, while both entries remain in the log.

**A30. Can anything other than a credit or debit be reversed?**
*Chosen:* no. Reversing an authorization, settlement or fee is refused. A
second reversal of the same event is refused.

**A31. May a value date be later than the booking day?**
Not in the stream. *Chosen:* allowed within the window; the entry simply
does not count until its value date.

**A32. "Three equal instalments" of 10.000.**
Impossible at 3 decimals. *Chosen:* 3.334, 3.333, 3.333, extra unit first.
All three are posted on Day 5 with value date Day 5, since E10 gives one
date; "instalments" is read as a split, not a schedule.

**A33. Input amounts with more decimals than the currency allows.**
R3 says amounts are "stored and rounded to their own precision".
*Chosen:* computed amounts are rounded; instructed amounts that are too
precise are refused (`INVALID_AMOUNT`) rather than silently altered.

## Reporting

**A34. Which "closing ledger balance" is printed per day?**
After E7 and E9 a day has two: what the books showed when it closed, and
what it is by value date now.
*Chosen:* the per-day section prints the figure as known at that close,
after fees. A table at the end shows the restated figures beside them.

**A35. Does the Day 6 closing balance include capitalized interest?**
*Chosen:* yes, and the line says so.

**A36. What counts as an "error"?**
*Chosen:* the errors line carries both refusals (ERROR) and applied-but-
flagged events (WARNING), each labelled.

## Deliberately not handled

After a first version that handled many cases the stream never contains, the
ledger was cut back to what the brief exercises (see WORKLOG.md). These are
known and left out on purpose:

- duplicate event IDs, and booking or value dates outside Day 1-6
- a second authorization reusing an existing authorization ID
- warnings for A7, A19 and A28 above
- a reversal that states an amount different from the original
