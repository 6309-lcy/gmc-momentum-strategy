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
_DECISION_COLUMNS = ["signal_date", "fill_date", "ledger", "signal_risk",
                     "signal_drawdown", "target_scale"]
_RISK_COLUMNS = ["date", "ledger", "volatility", "drawdown", "weights", "covariance"]


def run_path(prices: pd.DataFrame, weights: pd.Series, rebalance_dates: list,
             capital=500e6, trading_cost=.001, borrow_rate=.02, record=True,
             decision_policy=None, risk_covariances=None) -> dict:
    """Run a synthetic adjusted-close path; dividends are already in the proxy.

    Rebalance dates are execution dates in the observed index. Orders use the
    preceding observed close's NAV and prices and fill fixed whole-unit changes
    at the execution close. The final close never rebalances. ``decision_policy``
    optionally scales targets using only information available at the preceding
    close; its mode is ``risk`` or ``loss``.
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
    if decision_policy is not None:
        if not isinstance(decision_policy, dict):
            raise ValueError("decision_policy must be a dict")
        mode = decision_policy.get("mode")
        threshold = decision_policy.get("threshold")
        factor = decision_policy.get("reduction_factor")
        if mode not in ("risk", "loss"):
            raise ValueError("decision_policy mode must be 'risk' or 'loss'")
        if not np.isfinite(threshold) or threshold <= 0:
            raise ValueError("decision_policy threshold must be positive and finite")
        if mode == 'loss' and (factor is None or not np.isfinite(factor) or factor < 0 or factor >= 1):
            raise ValueError("loss reduction_factor must be in [0,1)")
    dates = prices.index
    requested = pd.DatetimeIndex(rebalance_dates)
    if requested.hasnans or not requested.isin(dates).all():
        raise ValueError("rebalance dates must be observed price dates")
    execution = np.zeros(len(dates), dtype=bool)
    execution[dates.get_indexer(requested)] = True
    if decision_policy is not None:
        execution[1:-1] = True
    execution[0] = execution[-1] = False
    count = len(prices.columns)
    cov = None
    if risk_covariances is not None:
        cov = np.asarray(risk_covariances, dtype=float)
        if cov.shape != (len(dates), count, count) or not np.isfinite(cov).all():
            raise ValueError("risk_covariances must have annual shape (dates, assets, assets)")
    elif decision_policy is not None and decision_policy.get("mode") == "risk":
        raise ValueError("risk decision_policy requires risk_covariances")

    elapsed = np.zeros(len(dates))
    elapsed[1:] = np.diff(dates.as_unit("ns").asi8) / (86400e9)
    q = np.zeros((2, count))
    cash = np.full(2, float(capital))
    previous_nav = np.full(2, float(capital))
    peak = np.full(2, float(capital))
    fees = np.array([trading_cost, 0.])
    borrow_rates = np.array([borrow_rate, 0.])
    pnl = np.zeros((2, count))
    total_transaction = np.zeros(count)
    total_borrow = np.zeros(count)
    values = np.zeros((len(dates), len(_NAV_COLUMNS)))
    orders, trades, costs, positions, decisions, risk_rows = [], [], [], [], [], []
    scales = np.ones(2)
    loss_fired = np.zeros(2, dtype=bool)
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
            orders.append((dates[i], signal_date, prices.columns[j], delta[j],
                           reference_prices[j], reference_nav, kind, False))
            trades.append((dates[i], signal_date, prices.columns[j], delta[j], p[i, j],
                           delta[j] * p[i, j], transaction[j], kind, False))
            costs.append((dates[i], prices.columns[j], "transaction", transaction[j], False))

    for i, date in enumerate(dates):
        borrow = np.zeros((2, count))
        if i:
            pnl += q * (p[i] - p[i - 1])
            borrow = np.maximum(-q * p[i - 1], 0.) * (borrow_rates * elapsed[i] / 365.)[:, None]
            cash -= borrow.sum(axis=1)
            total_borrow += borrow[0]
            if record:
                for j in np.flatnonzero(borrow[0]):
                    costs.append((date, prices.columns[j], "borrow", borrow[0, j], False))
        short = np.maximum(-q * p[i], 0.).sum(axis=1)
        nav = cash + q @ p[i]
        check_state(nav, cash - short, date, "before execution")
        drawdown = nav / peak - 1.
        transaction = np.zeros((2, count))
        turnover = 0.
        target_scales = scales.copy()
        if i == 0 or execution[i]:
            if i == 0:
                target = np.repeat(w[None, :], 2, axis=0)
                delta = target * float(capital) / p[0]
                kind = "initial_close_diagnostic"
            else:
                old_scales = scales.copy()
                if decision_policy is not None:
                    for ledger in range(2):
                        signal_risk = np.nan
                        signal_drawdown = np.nan
                        if mode == "risk":
                            signal_risk = float(np.sqrt(max(0., (q[ledger] * p[i - 1] / previous_nav[ledger]) @ cov[i - 1] @ (q[ledger] * p[i - 1] / previous_nav[ledger]))))
                            original_vol = float(np.sqrt(max(0., w @ cov[i - 1] @ w)))
                            if original_vol > 0 and signal_risk > threshold:
                                scales[ledger] = min(scales[ledger], threshold / original_vol)
                        else:
                            signal_drawdown = float(previous_nav[ledger] / peak[ledger] - 1.)
                            if signal_drawdown <= -threshold and not loss_fired[ledger]:
                                scales[ledger] *= factor
                                loss_fired[ledger] = True
                        decisions.append((dates[i - 1], date, "net" if ledger == 0 else "gross",
                                           signal_risk, signal_drawdown, scales[ledger]))
                target_scales = scales.copy()
                delta = np.rint((w[None, :] * target_scales[:, None] * previous_nav[:, None] / p[i - 1]) - q)
                if decision_policy is not None:
                    delta[scales >= old_scales] = 0.
                kind = "rebalance" if decision_policy is None else f'{mode}_reduction'
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
        current_weights = q * p[i] / nav[:, None]
        covariance = cov[i] if cov is not None else None
        risk = np.nan
        if covariance is not None:
            risk = float(np.sqrt(max(0., current_weights[0] @ covariance @ current_weights[0])))
        risk_rows.append((date, "net", risk, float(nav[0] / max(peak[0], nav[0]) - 1.),
                          current_weights[0].copy(), covariance))
        if record:
            for j, ticker in enumerate(prices.columns):
                weight = current_weights[0, j]
                positions.append((date, ticker, q[0, j], p[i, j], q[0, j] * p[i, j],
                                  weight, w[j]*scales[0], weight-w[j]*scales[0]))
        peak = np.maximum(peak, nav)
        previous_nav = nav

    exit_cost = np.abs(q[0] * p[-1]) * trading_cost
    if record:
        for j in np.flatnonzero(q[0]):
            trades.append((dates[-1], dates[-1], prices.columns[j], -q[0, j], p[-1, j],
                           -q[0, j] * p[-1, j], exit_cost[j], "liquidation", True))
            costs.append((dates[-1], prices.columns[j], "liquidation", exit_cost[j], True))
    attribution = pd.DataFrame({
        "gross_stock_pnl": pnl[1], "stock_pnl": pnl[0],
        "transaction_cost": total_transaction, "borrow_cost": total_borrow,
        "net_pnl": pnl[0] - total_transaction - total_borrow,
        "liquidation_cost": exit_cost,
        "liquidation_pnl": pnl[0] - total_transaction - total_borrow - exit_cost,
    }, index=prices.columns)
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
        "decision_log": pd.DataFrame.from_records(decisions, columns=_DECISION_COLUMNS),
        "risk_history": pd.DataFrame.from_records(risk_rows, columns=_RISK_COLUMNS),
    }
