"""Business constants. Each one is justified in NUMBERS.md."""

from decimal import Decimal

# Days in the replay window; interest capitalizes at the close of the last one.
WINDOW_DAYS = 6

# Overdraft fee per currency (R1). The brief defines AED only.
OVERDRAFT_FEE = {"AED": Decimal("25.00")}

# 0.04% per day (R2).
DAILY_INTEREST_RATE = Decimal("0.0004")
