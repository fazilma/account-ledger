# Worklog

Times are local (IST) and taken from the system clock when the line was written.
Entries for 11 and 12 October carry a date only: the exact times were not recorded.

- 2026-10-11 — Read the brief. Restructured it into rules, event stream, criteria and deliverables (now BRIEF.md).
- 2026-10-12 — Worked the event stream by hand and judged C1-C8. Verdict: refuse C2, C4, C6, C7, C8. Listed ambiguities and wrote the phase plan.
- 2026-10-13 — Plan approved: Python standard library only; C4 refused, Auth-Z to be force-posted and flagged.
- 2026-10-13 11:36 — Checked environment: Python 3.14.6, git 2.50.1, empty folder, not yet a repository.
- 2026-10-13 11:40 — Repository initialised, scaffold committed. Local hooks require a stated justification before each new file; complied each time.
- 2026-10-13 11:40 — money.py: per-currency precision, half-even rounding, refusal of over-precise inputs, exact split in minor units. 11 tests pass.
- 2026-10-13 11:41 — core.py: frozen Event/Posting/Notice records, append-only logs, balance by value date, credits, debits, instalments, reversal as compensating postings, refusals recorded as notices. 23 tests pass.
- 2026-10-13 11:42 — Authorizations: append-only AuthRecord log, holds, available balance, approve/decline at exactly zero boundary, settlement releasing the whole hold, force-post for unmatched and declined settlements, duplicate settlement refused. 35 tests pass.
- 2026-10-13 11:43 — Day close: retroactive fee sweep (one fee per negative day, value-dated the day assessed), interest by rounding the running total, single capitalization on Day 6, per-account lazy closing, late bookings flagged, window closes for good. First run had 1 failure of 52: my own test expected 415.00 on Day 6 and forgot three days of interest (0.50). Fixed the test to assert Day 5; the ledger was right. 52 pass.
