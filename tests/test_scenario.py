"""The brief's event stream, checked against its acceptance criteria.

Accepted criteria are asserted as written. Refused criteria (C2, C4, C6, C7,
C8; see REJECTED.md) are asserted as what the ledger does instead.
"""

import unittest
from decimal import Decimal

from ledger.core import APPROVED, DECLINED, FEE, FORCE_POST, INTEREST, SETTLED
from ledger.replay import STREAM, render, replay

D = Decimal
A = "ACC-001"
B = "ACC-002"

# The same stream with E7 and its reversal E9 removed: "what if E7 never happened".
WITHOUT_E7 = tuple(e for e in STREAM if e.id not in ("E7", "E9"))


def fees(ledger):
    return [p for p in ledger.postings if p.kind == FEE]


class AcceptedCriteriaTest(unittest.TestCase):
    def test_c1_day2_closing_at_end_of_day5_before_fees_is_minus_370(self):
        l = replay(upto="E8")
        self.assertEqual(fees(l), [])
        self.assertEqual(l.balance(A, 2), D("-370.00"))

    def test_c3_auth_a_settlement_is_accepted(self):
        l = replay()
        self.assertIn("E5", [e.id for e in l.events])
        auth = l.auth_states(A)["Auth-A"]
        self.assertEqual((auth.state, auth.settled, auth.hold), (SETTLED, D("185.00"), D("200.00")))
        self.assertEqual([n for n in l.notices if n.event_id == "E5"], [])

    def test_c5_an_approved_auth_b_reduces_available_but_not_ledger(self):
        # In the real stream Auth-B is declined (see below), so the criterion
        # is checked on the stream without E7, where it is approved.
        before = replay(WITHOUT_E7, upto="E6")
        l = replay(WITHOUT_E7, upto="E8")
        self.assertEqual(l.auth_states(A)["Auth-B"].state, APPROVED)
        self.assertEqual(l.balance(A, 5), before.balance(A, 5))
        self.assertEqual(l.available(A, 5), before.available(A, 5) - D("90.00"))

    def test_c5_in_the_real_stream_auth_b_is_declined(self):
        l = replay()
        auth = l.auth_states(A)["Auth-B"]
        self.assertEqual(auth.state, DECLINED)
        self.assertEqual(l.holds(A), D("0"))


class RefusedCriteriaTest(unittest.TestCase):
    def test_c2_e7_causes_three_fees_all_assessed_on_day_5(self):
        l = replay()
        self.assertEqual([(f.for_day, f.booked_day, f.value_date) for f in fees(l)], [(2, 5, 5), (4, 5, 5), (5, 5, 5)])
        self.assertEqual(sum(f.amount for f in fees(l)), D("-75.00"))
        self.assertEqual(fees(replay(WITHOUT_E7)), [])

    def test_c4_unmatched_settlement_is_posted_and_flagged_not_refused(self):
        l = replay()
        (posting,) = [p for p in l.postings if p.event_id == "E6"]
        self.assertEqual((posting.kind, posting.amount), (FORCE_POST, D("-180.00")))
        (notice,) = [n for n in l.notices if n.event_id == "E6"]
        self.assertEqual((notice.severity, notice.code), ("WARNING", "UNMATCHED_SETTLEMENT"))

    def test_c6_after_e9_fees_and_the_auth_b_decision_do_not_revert(self):
        l = replay()
        never = replay(WITHOUT_E7)
        # The principal is restored: every day's balance differs only by fees and interest.
        self.assertEqual(l.balance(A, 4), never.balance(A, 4))
        # But the three fees stay booked, Auth-B stays declined, interest is lower.
        self.assertEqual(len(fees(l)), 3)
        self.assertEqual(l.auth_states(A)["Auth-B"].state, DECLINED)
        self.assertEqual(never.auth_states(A)["Auth-B"].state, APPROVED)
        self.assertEqual(l.balance(A, 6), D("210.74"))
        self.assertEqual(never.balance(A, 6), D("285.80"))
        # And E7 itself is still in the log, next to its reversal (R4).
        self.assertEqual([p.amount for p in l.postings if "E7" in (p.event_id, p.reverses)], [D("-620.00"), D("620.00")])

    def test_c7_instalments_are_3334_3333_3333_and_sum_to_10(self):
        l = replay()
        parts = [p.amount for p in l.postings if p.event_id == "E10"]
        self.assertEqual(parts, [D("3.334"), D("3.333"), D("3.333")])
        self.assertEqual(sum(parts), D("10.000"))

    def test_c8_no_remainder_is_discarded(self):
        l = replay()
        for account, total in ((A, D("0.74")), (B, D("0.008"))):
            accrued = sum(c.accrued for c in l.closes if c.account == account)
            (cap,) = [p.amount for p in l.postings if p.account == account and p.kind == INTEREST]
            self.assertEqual((accrued, cap), (total, total))


class ReplayTest(unittest.TestCase):
    def test_closing_balances_as_known_at_each_close(self):
        l = replay()
        closing = lambda account: [str(c.closing) for c in l.closes if c.account == account]
        self.assertEqual(closing(A), ["250.00", "250.00", "650.00", "285.00", "-410.00", "210.74"])
        self.assertEqual(closing(B), ["0.000", "0.000", "0.000", "0.000", "10.000", "10.008"])

    def test_daily_accruals(self):
        l = replay()
        self.assertEqual(
            [str(c.accrued) for c in l.closes if c.account == A],
            ["0.10", "0.10", "0.26", "0.11", "-0.46", "0.63"],
        )

    def test_listing_e10_after_e9_changes_nothing(self):
        in_day_order = tuple(sorted(STREAM, key=lambda e: e.booked_day))
        self.assertNotEqual(in_day_order, STREAM)
        self.assertEqual(replay(in_day_order).closes, replay().closes)

    def test_all_events_applied_with_one_warning(self):
        l = replay()
        self.assertEqual(len(l.events), 10)
        self.assertEqual([n.code for n in l.notices], ["UNMATCHED_SETTLEMENT"])

    def test_report_covers_every_day(self):
        report = render(replay())
        for day in range(1, 7):
            self.assertIn(f"=== Day {day} ===", report)
        for label in ("closing ledger", "fees assessed", "authorizations", "errors"):
            self.assertIn(label, report)


if __name__ == "__main__":
    unittest.main()
