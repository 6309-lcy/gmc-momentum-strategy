"""Order sizing for adjusted-close diagnostic execution."""

import numpy as np
import pandas as pd


def round_orders(target_weights, nav, previous_prices, quantities):
    """Return signed nearest-whole-unit orders using only the preceding close.

    Existing fractional entry units are retained; rounding applies to the trade,
    not the resulting position. Half-unit ties use NumPy's ties-to-even rule.
    """
    if not isinstance(target_weights, pd.Series) or target_weights.empty:
        raise ValueError("target_weights must be a nonempty Series")
    if not target_weights.index.is_unique:
        raise ValueError("target_weights must have unique asset labels")
    if not np.isfinite(nav) or nav <= 0:
        raise ValueError("nav must be positive and finite")
    index = target_weights.index

    def aligned(value, name):
        if isinstance(value, pd.Series):
            if not value.index.is_unique or set(value.index) != set(index):
                raise ValueError(f"{name} must match target_weights labels")
            value = value.reindex(index)
        array = np.asarray(value, dtype=float)
        if array.shape != (len(index),) or not np.isfinite(array).all():
            raise ValueError(f"{name} must be a finite vector matching weights")
        return array

    weights = aligned(target_weights, "target_weights")
    prices = aligned(previous_prices, "previous_prices")
    current = aligned(quantities, "quantities")
    if (prices <= 0).any():
        raise ValueError("previous_prices must be strictly positive")
    with np.errstate(over="ignore", invalid="ignore"):
        orders = np.rint(weights * float(nav) / prices - current)
    if not np.isfinite(orders).all():
        raise ValueError("order sizing overflowed")
    return pd.Series(orders, index=index, name="quantity")
