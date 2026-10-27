"""Causal adaptive covariance estimates for simulated price paths."""

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


def causal_covariances(training: pd.DataFrame, prices: pd.DataFrame, decay=.94) -> np.ndarray:
    """Return annualized causal covariance estimates for each simulated date.

    The initial estimate is Ledoit-Wolf covariance of training returns. Later
    estimates apply a zero-mean EWMA second moment to completed simulated
    returns; the training-to-entry bridge is deliberately excluded.
    """
    if not isinstance(training, pd.DataFrame) or training.empty:
        raise ValueError("training must be a nonempty DataFrame")
    if not isinstance(prices, pd.DataFrame) or prices.empty:
        raise ValueError("prices must be a nonempty DataFrame")
    for frame, name in ((training, "training"), (prices, "prices")):
        if not isinstance(frame.index, pd.DatetimeIndex):
            raise ValueError(f"{name} must have a DatetimeIndex")
        if frame.index.hasnans or not frame.index.is_unique or not frame.index.is_monotonic_increasing:
            raise ValueError(f"{name} dates must be unique, nonmissing, and increasing")
        if not frame.columns.is_unique:
            raise ValueError(f"{name} columns must be unique")
        if not np.isfinite(frame.to_numpy(dtype=float)).all() or (frame.to_numpy(dtype=float) <= 0).any():
            raise ValueError(f"{name} prices must be positive and finite")
    if list(training.columns) != list(prices.columns):
        raise ValueError("training and prices must have the same assets in the same order")
    if not np.isfinite(decay) or decay < 0 or decay > 1:
        raise ValueError("decay must be between 0 and 1")
    if prices.index[0] < training.index[-1]:
        raise ValueError("prices must not begin before training")
    train_returns = training.pct_change().iloc[1:].to_numpy(dtype=float)
    if train_returns.shape[0] < 2 or not np.isfinite(train_returns).all():
        raise ValueError("training must contain at least three valid price dates")
    lw = LedoitWolf().fit(train_returns)
    state = np.asarray(lw.covariance_, dtype=float) * 252.0
    output = np.empty((len(prices), len(prices.columns), len(prices.columns)), dtype=float)
    output[0] = state
    simulated = prices.to_numpy(dtype=float)
    for i in range(1, len(prices)):
        r = simulated[i] / simulated[i - 1] - 1.0
        state = decay * state + (1.0 - decay) * np.outer(r, r) * 252.0
        output[i] = state
    return output
