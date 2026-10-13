import unittest
from decimal import Decimal

from ledger.core import APPROVED, DECLINED, FORCE_POST, SETTLED
from tests.test_postings import codes, ev, new_ledger

D = Decimal


def state(ledger, auth_id, account="ACC-001"):
    return ledger.auth_states(account)[auth_id].state


class AuthorizationTest(unittest.TestCase):
    def setUp(self):
        self.l = new_ledger()
        self.l.apply(ev("E1", 1, "CREDIT", "250.00"))

    def test_approved_hold_reduces_available_not_ledger(self):
        self.l.apply(ev("E3", 2, "AUTHORIZATION", "200.00", auth_id="Auth-A"))
        self.assertEqual(state(self.l, "Auth-A"), APPROVED)
        self.assertEqual(self.l.balance("ACC-001", 2), D("250.00"))
        self.assertEqual(self.l.available("ACC-001", 2), D("50.00"))

    def test_approved_when_available_lands_exactly_on_zero(self):
        self.l.apply(ev("A", 2, "AUTHORIZATION", "250.00", auth_id="Auth-A"))
        self.assertEqual(state(self.l, "Auth-A"), APPROVED)
        self.assertEqual(self.l.available("ACC-001", 2), D("0.00"))

    def test_declined_one_minor_unit_over_and_a_decline_is_not_an_error(self):
        self.assertTrue(self.l.apply(ev("A", 2, "AUTHORIZATION", "250.01", auth_id="Auth-A")))
        self.assertEqual(state(self.l, "Auth-A"), DECLINED)
        self.assertEqual(self.l.holds("ACC-001"), D("0"))
        self.assertEqual(codes(self.l), [])

    def test_existing_holds_count_against_a_new_authorization(self):
        self.l.apply(ev("A", 2, "AUTHORIZATION", "200.00", auth_id="Auth-A"))
        self.l.apply(ev("B", 2, "AUTHORIZATION", "60.00", auth_id="Auth-B"))
        self.assertEqual(state(self.l, "Auth-B"), DECLINED)


class SettlementTest(unittest.TestCase):
    def setUp(self):
        self.l = new_ledger()
        self.l.apply(ev("E1", 1, "CREDIT", "650.00"))
        self.l.apply(ev("E3", 2, "AUTHORIZATION", "200.00", auth_id="Auth-A"))

    def test_settlement_below_hold_posts_amount_and_releases_whole_hold(self):
        self.assertTrue(self.l.apply(ev("E5", 4, "SETTLEMENT", "185.00", auth_id="Auth-A")))
        self.assertEqual(state(self.l, "Auth-A"), SETTLED)
        self.assertEqual(self.l.balance("ACC-001", 4), D("465.00"))
        self.assertEqual(self.l.holds("ACC-001"), D("0"))
        self.assertEqual(self.l.available("ACC-001", 4), D("465.00"))
        self.assertEqual(codes(self.l), [])

    def test_unmatched_settlement_is_force_posted_and_flagged(self):
        self.assertTrue(self.l.apply(ev("E6", 4, "SETTLEMENT", "180.00", auth_id="Auth-Z")))
        self.assertEqual(self.l.balance("ACC-001", 4), D("470.00"))
        self.assertEqual(self.l.postings[-1].kind, FORCE_POST)
        self.assertEqual(codes(self.l), ["UNMATCHED_SETTLEMENT"])
        self.assertNotIn("Auth-Z", self.l.auth_states("ACC-001"))

    def test_any_settlement_without_an_active_hold_is_force_posted(self):
        # Covers a declined authorization and a second settlement of a settled one.
        self.l.apply(ev("B", 3, "AUTHORIZATION", "900.00", auth_id="Auth-B"))
        self.l.apply(ev("S1", 4, "SETTLEMENT", "10.00", auth_id="Auth-B"))
        self.l.apply(ev("S2", 4, "SETTLEMENT", "185.00", auth_id="Auth-A"))
        self.l.apply(ev("S3", 4, "SETTLEMENT", "185.00", auth_id="Auth-A"))
        self.assertEqual([p.kind for p in self.l.postings[-3:]], [FORCE_POST, "SETTLEMENT", FORCE_POST])
        self.assertEqual(codes(self.l), ["UNMATCHED_SETTLEMENT", "UNMATCHED_SETTLEMENT"])
        self.assertEqual(state(self.l, "Auth-B"), DECLINED)

    def test_a_hold_on_one_account_does_not_match_a_settlement_on_another(self):
        self.l.apply(ev("S", 4, "SETTLEMENT", "1.000", auth_id="Auth-A", account="ACC-002"))
        self.assertEqual(codes(self.l), ["UNMATCHED_SETTLEMENT"])
        self.assertEqual(state(self.l, "Auth-A"), APPROVED)

    def test_a_settlement_cannot_be_reversed(self):
        self.l.apply(ev("E5", 4, "SETTLEMENT", "185.00", auth_id="Auth-A"))
        self.assertFalse(self.l.apply(ev("R", 5, "REVERSAL", reverses="E5")))
        self.assertEqual(codes(self.l), ["REVERSAL_TARGET_NOT_FOUND"])

    def test_auth_state_is_reported_as_known_on_each_day(self):
        self.l.apply(ev("E5", 4, "SETTLEMENT", "185.00", auth_id="Auth-A"))
        self.assertEqual(self.l.auth_states("ACC-001", 1), {})
        self.assertEqual(self.l.auth_states("ACC-001", 3)["Auth-A"].state, APPROVED)
        self.assertEqual(self.l.auth_states("ACC-001", 4)["Auth-A"].state, SETTLED)
        self.assertEqual(len(self.l.auth_records), 2)


if __name__ == "__main__":
    unittest.main()
