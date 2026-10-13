import unittest
from decimal import Decimal

from ledger.money import MoneyError, fmt, parse_amount, split_evenly, to_money


class ParseAmountTest(unittest.TestCase):
    def test_stores_at_currency_precision(self):
        self.assertEqual(str(parse_amount("1200", "AED")), "1200.00")
        self.assertEqual(str(parse_amount("10", "BHD")), "10.000")

    def test_refuses_excess_precision(self):
        with self.assertRaises(MoneyError):
            parse_amount("1.005", "AED")
        with self.assertRaises(MoneyError):
            parse_amount("1.0005", "BHD")

    def test_bhd_keeps_third_decimal(self):
        self.assertEqual(parse_amount("1.005", "BHD"), Decimal("1.005"))

    def test_refuses_float_and_junk(self):
        for bad in (1.1, "abc", None, "NaN", "Infinity"):
            with self.assertRaises(MoneyError):
                parse_amount(bad, "AED")

    def test_refuses_unknown_currency(self):
        with self.assertRaises(MoneyError):
            parse_amount("1.00", "USD")


class RoundingTest(unittest.TestCase):
    def test_half_even(self):
        self.assertEqual(to_money(Decimal("0.125"), "AED"), Decimal("0.12"))
        self.assertEqual(to_money(Decimal("0.135"), "AED"), Decimal("0.14"))


class SplitTest(unittest.TestCase):
    def test_three_way_bhd_split_sums_exactly(self):
        parts = split_evenly(Decimal("10.000"), 3, "BHD")
        self.assertEqual(parts, [Decimal("3.334"), Decimal("3.333"), Decimal("3.333")])
        self.assertEqual(sum(parts), Decimal("10.000"))

    def test_even_split(self):
        self.assertEqual(split_evenly(Decimal("9.00"), 3, "AED"), [Decimal("3.00")] * 3)

    def test_split_always_sums_to_total(self):
        for cents in range(0, 500, 7):
            total = Decimal(cents) / 100
            for n in (1, 2, 3, 7):
                self.assertEqual(sum(split_evenly(total, n, "AED")), total)

    def test_refuses_zero_parts(self):
        with self.assertRaises(MoneyError):
            split_evenly(Decimal("1.00"), 0, "AED")


class FormatTest(unittest.TestCase):
    def test_format(self):
        self.assertEqual(fmt(Decimal("-1370.5"), "AED"), "AED -1,370.50")
        self.assertEqual(fmt(Decimal("10"), "BHD"), "BHD 10.000")


if __name__ == "__main__":
    unittest.main()
