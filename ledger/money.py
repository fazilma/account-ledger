"""Currency precision, rounding and exact splitting. Decimal only, never float."""

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

# Decimal places per currency (R3). See NUMBERS.md.
PRECISION = {"AED": 2, "BHD": 3}

# Applied only to amounts the ledger computes (interest). See NUMBERS.md.
ROUNDING = ROUND_HALF_EVEN


class MoneyError(ValueError):
    """An amount that cannot be represented in its currency."""


def quantum(currency):
    """Smallest representable unit: 0.01 for AED, 0.001 for BHD."""
    if currency not in PRECISION:
        raise MoneyError(f"unknown currency {currency!r}")
    return Decimal(1).scaleb(-PRECISION[currency])


def to_money(value, currency):
    """Round a computed Decimal to the currency's precision."""
    return value.quantize(quantum(currency), rounding=ROUNDING)


def parse_amount(value, currency):
    """Validate an input amount and store it at the currency's precision.

    Inputs finer than the currency allows are refused rather than rounded:
    silently changing an instructed amount would hide an upstream fault.
    """
    if isinstance(value, float):
        raise MoneyError("float amounts are not accepted; pass a string or Decimal")
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise MoneyError(f"not a number: {value!r}") from None
    if not amount.is_finite():
        raise MoneyError(f"not a finite amount: {value!r}")
    rounded = to_money(amount, currency)
    if rounded != amount:
        raise MoneyError(
            f"{value} has more than {PRECISION[currency]} decimal places for {currency}"
        )
    return rounded


def split_evenly(total, parts, currency):
    """Split total into `parts` amounts that sum exactly to total.

    Works in whole minor units. When total does not divide evenly, the first
    instalments each carry one extra minor unit.
    """
    if parts < 1:
        raise MoneyError("parts must be at least 1")
    unit = quantum(currency)
    units = int(total / unit)
    base, extra = divmod(units, parts)
    return [(base + (1 if i < extra else 0)) * unit for i in range(parts)]


def fmt(amount, currency):
    return f"{currency} {amount:,.{PRECISION[currency]}f}"
