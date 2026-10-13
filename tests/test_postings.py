import dataclasses
import unittest
from decimal import Decimal

from ledger.core import Event, Ledger

D = Decimal


def new_ledger(**kw):
    return Ledger({"ACC-001": "AED", "ACC-002": "BHD"}, last_day=6, **kw)


def ev(id, day, type, amount=None, value_date=None, account="ACC-001", **kw):
    return Event(
        id=id, booked_day=day, type=type, account=account, amount=amount,
        value_date=day if value_date is None else value_date, **kw,
    )


def codes(ledger):
    return [n.code for n in ledger.notices]


class BalanceTest(unittest.TestCase):
    def test_opening_balance_is_zero_at_currency_precision(self):
        self.assertEqual(str(new_ledger().balance("ACC-001")), "0.00")
        self.assertEqual(str(new_ledger().balance("ACC-002")), "0.000")

    def test_credit_and_debit(self):
        l = new_ledger()
        l.apply(ev("E1", 1, "CREDIT", "1200.00"))
        l.apply(ev("E2", 1, "DEBIT", "950.00"))
        self.assertEqual(l.balance("ACC-001", 1), D("250.00"))

    def test_balance_is_by_value_date_not_booking_day(self):
        l = new_ledger()
        l.apply(ev("E1", 1, "CREDIT", "250.00"))
        l.apply(ev("E7", 5, "DEBIT", "620.00", value_date=2))
        self.assertEqual(l.balance("ACC-001", 1), D("250.00"))
        self.assertEqual(l.balance("ACC-001", 2), D("-370.00"))

    def test_debit_may_overdraw(self):
        l = new_ledger()
        self.assertTrue(l.apply(ev("E1", 1, "DEBIT", "10.00")))
        self.assertEqual(l.balance("ACC-001", 1), D("-10.00"))

    def test_instalments_sum_to_the_instructed_amount(self):
        l = new_ledger()
        l.apply(ev("E10", 5, "CREDIT", "10.000", account="ACC-002", instalments=3))
        amounts = [p.amount for p in l.postings]
        self.assertEqual(amounts, [D("3.334"), D("3.333"), D("3.333")])
        self.assertEqual(l.balance("ACC-002", 5), D("10.000"))


class ReversalTest(unittest.TestCase):
    def setUp(self):
        self.l = new_ledger()
        self.l.apply(ev("E1", 1, "CREDIT", "250.00"))
        self.l.apply(ev("E7", 5, "DEBIT", "620.00", value_date=2))

    def test_reversal_appends_and_keeps_the_original(self):
        before = self.l.postings
        self.assertTrue(self.l.apply(ev("E9", 6, "REVERSAL", value_date=2, reverses="E7")))
        self.assertEqual(self.l.postings[: len(before)], before)
        self.assertEqual(self.l.postings[-1].amount, D("620.00"))
        self.assertEqual(self.l.balance("ACC-001", 2), D("250.00"))

    def test_cannot_reverse_twice(self):
        self.l.apply(ev("E9", 6, "REVERSAL", value_date=2, reverses="E7"))
        self.assertFalse(self.l.apply(ev("E9b", 6, "REVERSAL", value_date=2, reverses="E7")))
        self.assertIn("ALREADY_REVERSED", codes(self.l))

    def test_cannot_reverse_unknown_event(self):
        self.assertFalse(self.l.apply(ev("E9", 6, "REVERSAL", reverses="E99")))
        self.assertIn("REVERSAL_TARGET_NOT_FOUND", codes(self.l))

    def test_reversal_amount_must_match_when_given(self):
        self.assertFalse(self.l.apply(ev("E9", 6, "REVERSAL", "600.00", reverses="E7")))
        self.assertIn("REVERSAL_AMOUNT_MISMATCH", codes(self.l))


class RefusalTest(unittest.TestCase):
    def assertRefused(self, event, code):
        l = new_ledger()
        l.apply(ev("E1", 1, "CREDIT", "1.00"))
        self.assertFalse(l.apply(event))
        self.assertEqual(codes(l), [code])
        self.assertEqual(len(l.postings), 1)

    def test_refusals_leave_no_posting(self):
        self.assertRefused(ev("E1", 1, "CREDIT", "5.00"), "DUPLICATE_EVENT")
        self.assertRefused(ev("X", 1, "CREDIT", "5.00", account="ACC-999"), "UNKNOWN_ACCOUNT")
        self.assertRefused(ev("X", 7, "CREDIT", "5.00"), "DAY_OUT_OF_WINDOW")
        self.assertRefused(ev("X", 1, "CREDIT", "5.00", currency="BHD"), "CURRENCY_MISMATCH")
        self.assertRefused(ev("X", 1, "CREDIT", "5.001"), "INVALID_AMOUNT")
        self.assertRefused(ev("X", 1, "CREDIT", "-5.00"), "INVALID_AMOUNT")
        self.assertRefused(ev("X", 1, "CREDIT", "5.00", instalments=0), "INVALID_INSTALMENTS")
        self.assertRefused(ev("X", 1, "TELEPORT", "5.00"), "UNKNOWN_EVENT_TYPE")


class AppendOnlyTest(unittest.TestCase):
    def test_records_are_frozen(self):
        l = new_ledger()
        l.apply(ev("E1", 1, "CREDIT", "1.00"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            l.postings[0].amount = D("2.00")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            l.events[0].amount = "2.00"

    def test_exposed_logs_cannot_change_the_ledger(self):
        l = new_ledger()
        l.apply(ev("E1", 1, "CREDIT", "1.00"))
        self.assertIsInstance(l.postings, tuple)
        self.assertIsInstance(l.events, tuple)
        self.assertIsInstance(l.notices, tuple)


if __name__ == "__main__":
    unittest.main()
