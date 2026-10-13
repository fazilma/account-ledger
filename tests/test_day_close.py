import unittest
from decimal import Decimal

from ledger.core import FEE, INTEREST
from tests.test_postings import codes, ev, new_ledger

D = Decimal
A = "ACC-001"
B = "ACC-002"


def fees(ledger, account=A):
    return [p for p in ledger.postings if p.account == account and p.kind == FEE]


def accrued(ledger, account=A):
    return [a.amount for a in ledger.accruals if a.account == account]


class OverdraftFeeTest(unittest.TestCase):
    def test_no_fee_on_positive_or_zero_closing_balance(self):
        l = new_ledger()
        l.apply(ev("C", 1, "CREDIT", "10.00"))
        l.apply(ev("D", 2, "DEBIT", "10.00"))
        l.finish()
        self.assertEqual(fees(l), [])

    def test_fee_is_booked_with_value_date_of_the_day_assessed(self):
        l = new_ledger()
        l.apply(ev("D", 1, "DEBIT", "10.00"))
        l.close_day(A, 1)
        (fee,) = fees(l)
        self.assertEqual((fee.amount, fee.booked_day, fee.value_date, fee.for_day), (D("-25.00"), 1, 1, 1))
        self.assertEqual(l.closes[0].closing_before_fees, D("-10.00"))
        self.assertEqual(l.closes[0].closing, D("-35.00"))

    def test_one_fee_per_negative_day(self):
        l = new_ledger()
        l.apply(ev("D", 1, "DEBIT", "10.00"))
        l.apply(ev("C", 4, "CREDIT", "500.00"))
        l.finish()
        self.assertEqual([f.for_day for f in fees(l)], [1, 2, 3])
        self.assertEqual(l.balance(A, 5), D("415.00"))

    def test_backdated_debit_is_charged_when_it_becomes_known(self):
        l = new_ledger()
        l.apply(ev("C1", 1, "CREDIT", "250.00"))
        l.apply(ev("C2", 3, "CREDIT", "400.00"))
        l.apply(ev("D", 5, "DEBIT", "620.00", value_date=2))
        l.close_day(A, 5)
        # Day 2 is now -370 and is charged; Day 3 onward recovered to +30.
        self.assertEqual([(f.for_day, f.value_date) for f in fees(l)], [(2, 5)])
        self.assertEqual(l.closes[-1].fee_days, (2,))

    def test_a_day_is_never_charged_twice(self):
        l = new_ledger()
        l.apply(ev("D", 1, "DEBIT", "10.00"))
        l.apply(ev("C", 2, "CREDIT", "100.00"))
        l.finish()
        self.assertEqual([f.for_day for f in fees(l)], [1])

    def test_fees_booked_today_count_in_todays_closing_balance(self):
        # Literal reading of R1 ("all entries"): two backdated fees booked on
        # Day 3 take Day 3 from +40 to -10, so Day 3 is charged as well.
        l = new_ledger()
        l.apply(ev("C1", 1, "CREDIT", "100.00"))
        l.apply(ev("C2", 3, "CREDIT", "90.00"))
        l.apply(ev("D", 3, "DEBIT", "150.00", value_date=1))
        l.close_day(A, 3)
        self.assertEqual([f.for_day for f in fees(l)], [1, 2, 3])
        self.assertEqual(l.balance(A, 3), D("-35.00"))

    def test_currency_without_a_fee_warns_once_and_charges_nothing(self):
        l = new_ledger()
        l.apply(ev("D", 1, "DEBIT", "1.000", account=B))
        l.finish()
        self.assertEqual(fees(l, B), [])
        self.assertEqual(codes(l).count("NO_FEE_CONFIGURED"), 6)
        self.assertEqual(len({n.message for n in l.notices}), 6)


class InterestTest(unittest.TestCase):
    def test_daily_accrual_on_positive_balance(self):
        l = new_ledger()
        l.apply(ev("C", 1, "CREDIT", "250.00"))
        l.close_day(A, 1)
        self.assertEqual(accrued(l), [D("0.10")])

    def test_no_interest_on_negative_balance(self):
        l = new_ledger(overdraft_fee={})
        l.apply(ev("D", 1, "DEBIT", "250.00"))
        l.finish()
        self.assertEqual(accrued(l), [D("0.00")] * 6)
        self.assertEqual([p for p in l.postings if p.kind == INTEREST], [])

    def test_remainder_is_carried_not_discarded(self):
        # 285.00 earns 0.114 a day. Rounding each day alone would give
        # 6 x 0.11 = 0.66 and lose 0.024; the running total gives 0.68.
        l = new_ledger()
        l.apply(ev("C", 1, "CREDIT", "285.00"))
        l.finish()
        self.assertEqual(accrued(l), [D("0.11"), D("0.12"), D("0.11"), D("0.12"), D("0.11"), D("0.11")])
        self.assertEqual(sum(accrued(l)), D("0.68"))

    def test_capitalizes_once_at_end_of_last_day_for_exactly_the_accrued_sum(self):
        l = new_ledger()
        l.apply(ev("C", 1, "CREDIT", "285.00"))
        l.finish()
        (cap,) = [p for p in l.postings if p.kind == INTEREST]
        self.assertEqual(cap.amount, sum(accrued(l)))
        self.assertEqual((cap.booked_day, cap.value_date), (6, 6))
        self.assertEqual(l.balance(A, 6), D("285.68"))
        self.assertEqual(l.balance(A, 5), D("285.00"))

    def test_backdated_debit_restates_earlier_accruals(self):
        l = new_ledger(overdraft_fee={})
        l.apply(ev("C", 1, "CREDIT", "1000.00"))
        l.apply(ev("D", 3, "DEBIT", "1000.00", value_date=1))
        l.finish()
        # 0.40 accrued on each of Days 1 and 2 is taken back on Day 3.
        self.assertEqual(accrued(l), [D("0.40"), D("0.40"), D("-0.80"), D("0.00"), D("0.00"), D("0.00")])
        self.assertEqual([p for p in l.postings if p.kind == INTEREST], [])

    def test_accruals_always_sum_to_the_capitalized_total(self):
        for cents in range(1, 200000, 7919):
            for account, amount in ((A, f"{D(cents) / 100:.2f}"), (B, f"{D(cents) / 1000:.3f}")):
                l = new_ledger()
                l.apply(ev("C", 1, "CREDIT", amount, account=account))
                l.apply(ev("C2", 4, "CREDIT", amount, account=account, value_date=2))
                l.finish()
                cap = sum((p.amount for p in l.postings if p.kind == INTEREST), D(0))
                self.assertEqual(sum(accrued(l, account)), cap, (account, amount))


class CloseOrderTest(unittest.TestCase):
    def test_days_close_once_and_in_order(self):
        l = new_ledger()
        l.close_day(A, 1)
        for bad in (1, 3, 0):
            with self.assertRaises(ValueError):
                l.close_day(A, bad)

    def test_applying_an_event_closes_the_earlier_days_of_its_account_only(self):
        l = new_ledger()
        l.apply(ev("C", 4, "CREDIT", "1.00"))
        self.assertEqual(l.closed_through(A), 3)
        self.assertEqual(l.closed_through(B), 0)

    def test_event_for_an_already_closed_day_is_applied_and_flagged(self):
        l = new_ledger()
        l.apply(ev("C", 4, "CREDIT", "250.00"))
        self.assertTrue(l.apply(ev("L", 2, "CREDIT", "250.00")))
        self.assertEqual(codes(l), ["LATE_BOOKING"])
        l.finish()
        # Days 2 and 3 at 250.00 are accrued at the Day 4 close: 0.20 late, plus 0.20 for Day 4.
        self.assertEqual(accrued(l)[:4], [D("0.00"), D("0.00"), D("0.00"), D("0.40")])

    def test_nothing_is_accepted_after_the_window_is_closed(self):
        l = new_ledger()
        l.finish()
        self.assertFalse(l.apply(ev("C", 6, "CREDIT", "1.00")))
        self.assertEqual(codes(l), ["WINDOW_CLOSED"])


if __name__ == "__main__":
    unittest.main()
