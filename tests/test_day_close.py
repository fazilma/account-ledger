import unittest
from decimal import Decimal

from ledger.core import FEE, INTEREST
from tests.test_postings import ev, run

D = Decimal
A = "ACC-001"
B = "ACC-002"


def fees(ledger, account=A):
    return [p for p in ledger.postings if p.account == account and p.kind == FEE]


def accrued(ledger, account=A):
    return [c.accrued for c in ledger.closes if c.account == account]


def capitalized(ledger, account=A):
    return [p for p in ledger.postings if p.account == account and p.kind == INTEREST]


class OverdraftFeeTest(unittest.TestCase):
    def test_no_fee_on_positive_or_zero_closing_balance(self):
        l = run([ev("C", 1, "CREDIT", "10.00"), ev("D", 2, "DEBIT", "10.00")])
        self.assertEqual(fees(l), [])

    def test_fee_is_booked_with_value_date_of_the_day_assessed(self):
        l = run([ev("D", 1, "DEBIT", "10.00")], last=1)
        (fee,) = fees(l)
        self.assertEqual((fee.amount, fee.booked_day, fee.value_date, fee.for_day), (D("-25.00"), 1, 1, 1))
        self.assertEqual(l.closes[0].closing_before_fees, D("-10.00"))
        self.assertEqual(l.closes[0].closing, D("-35.00"))

    def test_one_fee_per_negative_day(self):
        l = run([ev("D", 1, "DEBIT", "10.00"), ev("C", 4, "CREDIT", "500.00")])
        self.assertEqual([f.for_day for f in fees(l)], [1, 2, 3])
        self.assertEqual(l.balance(A, 5), D("415.00"))

    def test_a_day_is_never_charged_twice(self):
        l = run([ev("D", 1, "DEBIT", "10.00"), ev("C", 2, "CREDIT", "100.00")])
        self.assertEqual([f.for_day for f in fees(l)], [1])

    def test_backdated_debit_is_charged_when_it_becomes_known(self):
        l = run([
            ev("C1", 1, "CREDIT", "250.00"),
            ev("C2", 3, "CREDIT", "400.00"),
            ev("D", 5, "DEBIT", "620.00", value_date=2),
        ])
        # Day 2 is now -370 and is charged on Day 5; Day 3 onward recovered to +30.
        self.assertEqual([(f.for_day, f.value_date) for f in fees(l)], [(2, 5)])

    def test_fees_booked_today_count_in_todays_closing_balance(self):
        # Literal reading of R1 ("all entries"): two backdated fees booked on
        # Day 3 take Day 3 from +40 to -10, so Day 3 is charged as well.
        l = run([
            ev("C1", 1, "CREDIT", "100.00"),
            ev("C2", 3, "CREDIT", "90.00"),
            ev("D", 3, "DEBIT", "150.00", value_date=1),
        ], last=3)
        self.assertEqual([f.for_day for f in fees(l)], [1, 2, 3])
        self.assertEqual(l.balance(A, 3), D("-35.00"))

    def test_currency_without_a_defined_fee_is_charged_nothing(self):
        l = run([ev("D", 1, "DEBIT", "1.000", account=B)])
        self.assertEqual(fees(l, B), [])
        self.assertEqual(l.balance(B, 6), D("-1.000"))


class InterestTest(unittest.TestCase):
    def test_daily_accrual_on_positive_balance(self):
        l = run([ev("C", 1, "CREDIT", "250.00")], last=1)
        self.assertEqual(accrued(l), [D("0.10")])

    def test_no_interest_on_negative_balance(self):
        l = run([ev("D", 1, "DEBIT", "250.00")], overdraft_fee={})
        self.assertEqual(accrued(l), [D("0.00")] * 6)
        self.assertEqual(capitalized(l), [])

    def test_remainder_is_carried_not_discarded(self):
        # 285.00 earns 0.114 a day. Rounding each day alone would give
        # 6 x 0.11 = 0.66 and lose 0.024; the running total gives 0.68.
        l = run([ev("C", 1, "CREDIT", "285.00")])
        self.assertEqual(accrued(l), [D("0.11"), D("0.12"), D("0.11"), D("0.12"), D("0.11"), D("0.11")])
        self.assertEqual(sum(accrued(l)), D("0.68"))

    def test_capitalizes_once_at_end_of_last_day_for_exactly_the_accrued_sum(self):
        l = run([ev("C", 1, "CREDIT", "285.00")])
        (cap,) = capitalized(l)
        self.assertEqual(cap.amount, sum(accrued(l)))
        self.assertEqual((cap.booked_day, cap.value_date), (6, 6))
        self.assertEqual(l.balance(A, 5), D("285.00"))
        self.assertEqual(l.balance(A, 6), D("285.68"))

    def test_backdated_debit_restates_earlier_accruals(self):
        l = run(
            [ev("C", 1, "CREDIT", "1000.00"), ev("D", 3, "DEBIT", "1000.00", value_date=1)],
            overdraft_fee={},
        )
        # 0.40 accrued on each of Days 1 and 2 is taken back on Day 3.
        self.assertEqual(accrued(l), [D("0.40"), D("0.40"), D("-0.80"), D("0.00"), D("0.00"), D("0.00")])
        self.assertEqual(capitalized(l), [])

    def test_accruals_always_sum_to_the_capitalized_total(self):
        for cents in range(1, 200000, 7919):
            for account, amount in ((A, f"{D(cents) / 100:.2f}"), (B, f"{D(cents) / 1000:.3f}")):
                l = run([
                    ev("C", 1, "CREDIT", amount, account=account),
                    ev("C2", 4, "CREDIT", amount, account=account, value_date=2),
                ])
                cap = sum((p.amount for p in capitalized(l, account)), D(0))
                self.assertEqual(sum(accrued(l, account)), cap, (account, amount))


if __name__ == "__main__":
    unittest.main()
