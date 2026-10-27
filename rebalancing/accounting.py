"""Self-financing adjusted-close diagnostics with independent net/gross ledgers."""

import numpy as np
import pandas as pd


_NAV_COLUMNS = [
    "nav", "gross_nav", "cash", "restricted_cash", "available_cash",
    "short_market_value", "transaction_cost", "borrow_cost", "turnover",
    "liquidation_nav",
]
_ORDER_COLUMNS = ["date", "signal_date", "ticker", "quantity", "reference_price",
                  "reference_nav", "kind", "hypothetical"]
_TRADE_COLUMNS = ["date", "signal_date", "ticker", "quantity", "price", "notional",
                  "transaction_cost", "kind", "hypothetical"]
_COST_COLUMNS = ["date", "ticker", "kind", "amount", "hypothetical"]


def run_path(prices: pd.DataFrame, weights: pd.Series, rebalance_dates: list,
             capital=500e6, trading_cost=.001, borrow_rate=.02, record=True) -> dict:
    """Run a synthetic adjusted-close path; dividends are already in the proxy.

    Rebalance dates are execution dates in the observed index. Orders use the
    preceding observed close's NAV and prices and fill fixed whole-unit changes
    at the execution close. Entry alone uses fractional units at the first close.
    The final close never rebalances. Cash earns zero; short proceeds are held
    as cash, with current short market value restricted as collateral.

    ``record=False`` suppresses order, trade, and cost detail, retaining NAV and
    attribution. Turnover is absolute traded notional / preceding close NAV
    (starting capital at entry). Hypothetical exit costs never reduce MTM NAV.
    """
    if not isinstance(prices, pd.DataFrame) or prices.empty:
        raise ValueError("prices must be a nonempty DataFrame")
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("prices must have a DatetimeIndex")
    if prices.index.hasnans or not prices.index.is_unique or not prices.index.is_monotonic_increasing:
        raise ValueError("price dates must be unique, nonmissing, and increasing")
    if not prices.columns.is_unique:
        raise ValueError("price columns must be unique")
    if not isinstance(weights, pd.Series) or weights.empty or not weights.index.is_unique:
        raise ValueError("weights must be a nonempty Series with unique labels")
    if set(weights.index) != set(prices.columns):
        raise ValueError("weights must match price columns exactly")
    p = prices.to_numpy(dtype=float)
    w = weights.reindex(prices.columns).to_numpy(dtype=float)
    if not np.isfinite(p).all() or (p <= 0).any():
        raise ValueError("prices must be positive and finite with no missing values")
    if not np.isfinite(w).all():
        raise ValueError("weights must be finite")
    if not np.isfinite(capital) or capital <= 0:
        raise ValueError("capital must be positive and finite")
    if not np.isfinite(trading_cost) or trading_cost < 0:
        raise ValueError("trading_cost must be finite and nonnegative")
    if not np.isfinite(borrow_rate) or borrow_rate < 0:
        raise ValueError("borrow_rate must be finite and nonnegative")
    dates = prices.index
    requested = pd.DatetimeIndex(rebalance_dates)
    if requested.hasnans or not requested.isin(dates).all():
        raise ValueError("rebalance dates must be observed price dates")
    execution = np.zeros(len(dates), dtype=bool)
    execution[dates.get_indexer(requested)] = True
    execution[0] = execution[-1] = False
    elapsed = np.zeros(len(dates))
    elapsed[1:] = np.diff(dates.as_unit("ns").asi8) / (86400e9)
    assets = prices.columns
    count = len(assets)
    q = np.zeros((2, count))
    cash = np.full(2, float(capital))
    previous_nav = np.full(2, float(capital))
    fees = np.array([trading_cost, 0.])
    borrow_rates = np.array([borrow_rate, 0.])
    pnl = np.zeros((2, count))
    total_transaction = np.zeros(count)
    total_borrow = np.zeros(count)
    values = np.zeros((len(dates), len(_NAV_COLUMNS)))
    orders, trades, costs, positions = [], [], [], []
    tolerance = max(1e-8, float(capital) * 1e-12)

    def check_state(nav, available, date, stage):
        if not np.isfinite(nav).all() or (nav <= 0).any():
            raise ValueError(f"Nonpositive or nonfinite NAV at {date} ({stage})")
        if not np.isfinite(available).all() or (available < -tolerance).any():
            raise ValueError(f"Insufficient available cash at {date} ({stage}); no financing injection")

    def record_fills(i, delta, transaction, kind, reference_nav):
        signal_date = dates[max(0, i - 1)]
        reference_prices = p[max(0, i - 1)]
        for j in np.flatnonzero(delta):
            orders.append((dates[i], signal_date, assets[j], delta[j],
                           reference_prices[j], reference_nav, kind, False))
            trades.append((dates[i], signal_date, assets[j], delta[j], p[i, j],
                           delta[j] * p[i, j], transaction[j], kind, False))
            costs.append((dates[i], assets[j], "transaction", transaction[j], False))

    for i, date in enumerate(dates):
        borrow = np.zeros((2, count))
        if i:
            pnl += q * (p[i] - p[i - 1])
            borrow = np.maximum(-q * p[i - 1], 0.) * (borrow_rates * elapsed[i] / 365.)[:, None]
            cash -= borrow.sum(axis=1)
            total_borrow += borrow[0]
            if record:
                for j in np.flatnonzero(borrow[0]):
                    costs.append((date, assets[j], "borrow", borrow[0, j], False))
        short = np.maximum(-q * p[i], 0.).sum(axis=1)
        nav = cash + q @ p[i]
        check_state(nav, cash - short, date, "before execution")
        transaction = np.zeros((2, count))
        turnover = 0.
        if i == 0 or execution[i]:
            if i == 0:
                delta = w[None, :] * float(capital) / p[0]
                delta = np.repeat(delta, 2, axis=0)
                kind = "initial_close_diagnostic"
            else:
                delta = np.rint(w[None, :] * previous_nav[:, None] / p[i - 1] - q)
                kind = "rebalance"
            transaction = np.abs(delta * p[i]) * fees[:, None]
            cash -= (delta * p[i]).sum(axis=1) + transaction.sum(axis=1)
            q += delta
            total_transaction += transaction[0]
            turnover = np.abs(delta[0] * p[i]).sum() / previous_nav[0]
            if record:
                record_fills(i, delta[0], transaction[0], kind, previous_nav[0])
        short = np.maximum(-q * p[i], 0.).sum(axis=1)
        nav = cash + q @ p[i]
        available = cash - short
        check_state(nav, available, date, "after execution")
        liquidation_cost = np.abs(q[0] * p[i]).sum() * trading_cost
        values[i] = (nav[0], nav[1], cash[0], short[0], available[0], short[0],
                     transaction[0].sum(), borrow[0].sum(), turnover, nav[0] - liquidation_cost)
        if record:
            for j, ticker in enumerate(assets):
                weight = q[0, j] * p[i, j] / nav[0]
                positions.append((date, ticker, q[0, j], p[i, j], q[0, j] * p[i, j], weight, w[j], weight-w[j]))
        previous_nav = nav

    exit_cost = np.abs(q[0] * p[-1]) * trading_cost
    if record:
        for j in np.flatnonzero(q[0]):
            trades.append((dates[-1], dates[-1], assets[j], -q[0, j], p[-1, j],
                           -q[0, j] * p[-1, j], exit_cost[j], "liquidation", True))
            costs.append((dates[-1], assets[j], "liquidation", exit_cost[j], True))
    attribution = pd.DataFrame({
        "gross_stock_pnl": pnl[1], "stock_pnl": pnl[0],
        "transaction_cost": total_transaction, "borrow_cost": total_borrow,
        "net_pnl": pnl[0] - total_transaction - total_borrow,
        "liquidation_cost": exit_cost,
        "liquidation_pnl": pnl[0] - total_transaction - total_borrow - exit_cost,
    }, index=assets)
    attribution.index.name = "ticker"
    nav_frame = pd.DataFrame(values, index=dates, columns=_NAV_COLUMNS)
    nav_frame.attrs["price_convention"] = "adjusted-close proxy; dividends included"
    nav_frame.attrs["initial_execution"] = "fractional initial-close diagnostic"
    return {
        "nav": nav_frame,
        "orders": pd.DataFrame.from_records(orders, columns=_ORDER_COLUMNS),
        "trades": pd.DataFrame.from_records(trades, columns=_TRADE_COLUMNS),
        "costs": pd.DataFrame.from_records(costs, columns=_COST_COLUMNS),
        "attribution": attribution,
        "terminal_notional": float(np.abs(q[0] * p[-1]).sum()),
        "daily_positions": pd.DataFrame(positions, columns=['date', 'ticker', 'quantity', 'price', 'market_value', 'weight', 'target_weight', 'weight_deviation']),
    }
