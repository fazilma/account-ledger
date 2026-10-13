import unittest
from decimal import Decimal

from ledger.core import APPROVED, DECLINED, SETTLED
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

    def test_declined_one_minor_unit_over(self):
        self.assertTrue(self.l.apply(ev("A", 2, "AUTHORIZATION", "250.01", auth_id="Auth-A")))
        self.assertEqual(state(self.l, "Auth-A"), DECLINED)
        self.assertEqual(self.l.holds("ACC-001"), D("0"))
        self.assertEqual(codes(self.l), [])

    def test_existing_holds_count_against_a_new_authorization(self):
        self.l.apply(ev("A", 2, "AUTHORIZATION", "200.00", auth_id="Auth-A"))
        self.l.apply(ev("B", 2, "AUTHORIZATION", "60.00", auth_id="Auth-B"))
        self.assertEqual(state(self.l, "Auth-B"), DECLINED)

    def test_duplicate_authorization_id_is_refused(self):
        self.l.apply(ev("A", 2, "AUTHORIZATION", "10.00", auth_id="Auth-A"))
        self.assertFalse(self.l.apply(ev("B", 2, "AUTHORIZATION", "10.00", auth_id="Auth-A")))
        self.assertIn("DUPLICATE_AUTHORIZATION", codes(self.l))

    def test_authorization_without_id_is_refused(self):
        self.assertFalse(self.l.apply(ev("A", 2, "AUTHORIZATION", "10.00")))
        self.assertIn("MISSING_AUTH_ID", codes(self.l))


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

    def test_settlement_above_hold_posts_and_warns(self):
        self.l.apply(ev("E5", 4, "SETTLEMENT", "230.00", auth_id="Auth-A"))
        self.assertEqual(self.l.balance("ACC-001", 4), D("420.00"))
        self.assertEqual(codes(self.l), ["OVER_SETTLEMENT"])

    def test_second_settlement_of_same_authorization_is_refused(self):
        self.l.apply(ev("E5", 4, "SETTLEMENT", "185.00", auth_id="Auth-A"))
        self.assertFalse(self.l.apply(ev("E5b", 4, "SETTLEMENT", "185.00", auth_id="Auth-A")))
        self.assertEqual(self.l.balance("ACC-001", 4), D("465.00"))
        self.assertEqual(codes(self.l), ["DUPLICATE_SETTLEMENT"])

    def test_unmatched_settlement_is_force_posted_and_flagged(self):
        self.assertTrue(self.l.apply(ev("E6", 4, "SETTLEMENT", "180.00", auth_id="Auth-Z")))
        self.assertEqual(self.l.balance("ACC-001", 4), D("470.00"))
        self.assertEqual(self.l.postings[-1].kind, "FORCE_POST")
        self.assertEqual(codes(self.l), ["UNMATCHED_SETTLEMENT"])
        self.assertNotIn("Auth-Z", self.l.auth_states("ACC-001"))

    def test_settlement_of_declined_authorization_is_force_posted_and_flagged(self):
        self.l.apply(ev("B", 3, "AUTHORIZATION", "900.00", auth_id="Auth-B"))
        self.l.apply(ev("S", 4, "SETTLEMENT", "900.00", auth_id="Auth-B"))
        self.assertEqual(self.l.balance("ACC-001", 4), D("-250.00"))
        self.assertEqual(state(self.l, "Auth-B"), DECLINED)
        self.assertEqual(codes(self.l), ["SETTLEMENT_OF_DECLINED_AUTH"])

    def test_a_settlement_cannot_be_reversed(self):
        self.l.apply(ev("E5", 4, "SETTLEMENT", "185.00", auth_id="Auth-A"))
        self.assertFalse(self.l.apply(ev("R", 5, "REVERSAL", reverses="E5")))
        self.assertEqual(codes(self.l), ["REVERSAL_TARGET_NOT_FOUND"])

    def test_a_hold_on_one_account_does_not_match_a_settlement_on_another(self):
        self.l.apply(ev("S", 4, "SETTLEMENT", "1.000", auth_id="Auth-A", account="ACC-002"))
        self.assertEqual(codes(self.l), ["UNMATCHED_SETTLEMENT"])
        self.assertEqual(state(self.l, "Auth-A"), APPROVED)

    def test_auth_state_is_reported_as_known_on_each_day(self):
        self.l.apply(ev("E5", 4, "SETTLEMENT", "185.00", auth_id="Auth-A"))
        self.assertEqual(self.l.auth_states("ACC-001", 1), {})
        self.assertEqual(self.l.auth_states("ACC-001", 3)["Auth-A"].state, APPROVED)
        self.assertEqual(self.l.auth_states("ACC-001", 4)["Auth-A"].state, SETTLED)
        self.assertEqual(len(self.l.auth_records), 2)


if __name__ == "__main__":
    unittest.main()
