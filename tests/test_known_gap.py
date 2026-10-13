"""The one deliberately failing test. It is expected to FAIL; do not "fix" it
by weakening the assertion.

WHAT IT ASSERTS
    When a debit is reversed in full, the overdraft fees that only that debit
    caused should net to zero for the customer.

WHAT HAPPENS
    E7 (a backdated AED 620.00 debit) pushes Days 2, 4 and 5 negative and the
    Day 5 close books three fees, AED 75.00. E9 then reverses E7 in full. The
    ledger restores the 620.00 and nothing else: the fees stay.

WHAT IT REVEALS ABOUT THE DESIGN
    1. Consequences are one-way. The ledger derives fees from balances when a
       day closes, but it keeps no link from a fee to the entry that caused
       it, so a reversal cannot find "its" fees. The same is true of the
       Auth-B decline, which E9 does not revisit.
    2. This is a policy gap, not an arithmetic one. Auto-refunding is not
       obviously right either: on Day 5 the books really were overdrawn, and
       the brief's C6 ("all balances and fees return") is refused in
       REJECTED.md because Auth-B and the event log cannot return. But a
       customer charged AED 75.00 for an entry the bank itself withdrew has a
       fair complaint, and this ledger gives an operator no way to see it.
    3. The honest fix is a new event type (FEE_WAIVER) plus a cause link on
       fee postings, so a reversal can list the fees it orphaned and a human
       or a rule can waive them with an append-only entry. That is out of the
       brief's scope and is left undone on purpose.

The same gap shows up in interest: the customer ends Day 6 with AED 0.74 of
interest instead of the 0.80 they would have earned had E7 never been booked,
because the three fees lowered the Day 5 and Day 6 balances.
"""

import unittest
from decimal import Decimal

from ledger.core import FEE
from ledger.replay import replay


class KnownGapTest(unittest.TestCase):
    def test_fees_caused_only_by_a_reversed_debit_net_to_zero(self):
        ledger = replay()
        net_fees = sum(p.amount for p in ledger.postings if p.kind == FEE)
        # FAILS: net_fees is -75.00. Three fees booked on Day 5 because of E7
        # survive E9's full reversal of E7.
        self.assertEqual(net_fees, Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
