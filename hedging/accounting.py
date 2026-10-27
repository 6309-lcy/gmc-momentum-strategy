"""Self-financing hedge overlay using fractional adjusted-close synthetic units."""

import numpy as np
import pandas as pd


def run_overlay(prices, signals, model, capital=200e6, stock_capital=500e6,
                trading_cost=.001, cash_buffer=.02, mode='dynamic', on_insufficient_cash='raise'):
    """Allocate the overlay between SGOV and SH without changing the stock account.

    Initialization is a same-close diagnostic using signal observation zero.
    Subsequent signal changes use the previous close's NAV and prices to fix
    quantities before filling at the current close. No new orders execute on
    the final observation (except initialization of a one-observation path).
    ``target_sh`` is the last ordered SH dollar target, not its marked value.
    Hypothetical terminal sales appear separately from actual cash flows.
    """
    if not isinstance(prices, pd.DataFrame) or prices.empty:
        raise ValueError('Prices require a nonempty DataFrame')
    dates = prices.index
    if (not isinstance(dates, pd.DatetimeIndex) or dates.hasnans
            or dates.has_duplicates or not dates.is_monotonic_increasing):
        raise ValueError('Prices require unique increasing valid dates')
    if prices.columns.has_duplicates or not {'SGOV', 'SH', 'SPY'}.issubset(prices.columns):
        raise ValueError('Prices require unique columns including SGOV, SH and SPY')
    try:
        panel = prices.astype(float)
    except (TypeError, ValueError) as exc:
        raise ValueError('Asset prices must be finite and positive') from exc
    if not np.isfinite(panel.to_numpy()).all() or (panel <= 0).any().any():
        raise ValueError('Asset prices must be finite and positive')
    if (not isinstance(signals, pd.DataFrame) or not signals.index.equals(dates)
            or signals.columns.has_duplicates or 'hedge_active' not in signals):
        raise ValueError('Signals must have the same dates and a hedge_active column')
    active = signals['hedge_active']
    if active.isna().any() or not active.isin([True, False]).all():
        raise ValueError('hedge_active must contain only boolean states')
    if mode not in ('dynamic', 'static', 'reserve'):
        raise ValueError('Mode must be dynamic, static or reserve')
    for name, value in (('capital', capital), ('stock_capital', stock_capital),
                        ('trading_cost', trading_cost), ('cash_buffer', cash_buffer)):
        if not np.isscalar(value) or not isinstance(value, (int, float, np.number)) or not np.isfinite(value):
            raise ValueError(f'{name} must be finite')
    if capital <= 0 or stock_capital < 0 or trading_cost < 0 or not 0 <= cash_buffer < 1:
        raise ValueError('Require capital > 0, stock_capital and trading_cost >= 0, and cash_buffer in [0,1)')
    if not isinstance(model, dict):
        raise ValueError('Model must be a dictionary containing a clipped beta')
    beta = next((model[key] for key in ('beta_clipped', 'hedge_beta', 'beta') if key in model), None)
    if (not isinstance(beta, (int, float, np.number)) or not np.isfinite(beta)
            or not 0 <= beta <= 1):
        raise ValueError('Model beta_clipped, hedge_beta or beta must be finite and in [0,1]')

    if on_insufficient_cash not in ('raise','reject'):
        raise ValueError('on_insufficient_cash must be raise or reject')
    rejections=[]
    tickers = ['SGOV', 'SH']
    p = panel[tickers].to_numpy()
    quantity = np.zeros(2)
    cash = float(capital)
    previous_nav = float(capital)
    previous_active = None
    target_sh = 0.
    nav_rows, orders, trades, positions, costs = [], [], [], [], []
    for i, date in enumerate(dates):
        signal_index = max(0, i - 1)
        signal_active = (bool(active.iloc[signal_index]) if mode == 'dynamic'
                         else mode == 'static')
        if i == len(dates)-1 and i > 0:
            signal_active = previous_active
        transaction = np.zeros(2)
        if i == 0 or (i < len(dates) - 1 and signal_active != previous_active):
            reference_prices = p[signal_index]
            investable = (1 - cash_buffer) * previous_nav
            target_sh = min(float(beta) * stock_capital, investable) if signal_active else 0.
            target = np.array([investable - target_sh, target_sh])
            delta = target / reference_prices - quantity
            notional = delta * p[i]
            transaction = np.abs(notional) * trading_cost
            next_cash = cash - notional.sum() - transaction.sum()
            if not np.isfinite(next_cash):
                raise ValueError('Nonfinite execution cash')
            if next_cash < 0:
                if on_insufficient_cash == 'raise':
                    raise ValueError(f'Insufficient cash at {date}: gap fills and fees exhaust buffer; no financing injection')
                rejections.append((date, dates[signal_index], next_cash, signal_active))
                delta = np.zeros(2)
                transaction = np.zeros(2)
                notional = np.zeros(2)
                next_cash = cash
                signal_active = previous_active
            cash = float(next_cash)
            quantity += delta
            kind = 'initial_close_diagnostic' if i == 0 else 'signal_change'
            for j in np.flatnonzero(delta):
                orders.append((date, dates[signal_index], tickers[j], delta[j],
                               reference_prices[j], previous_nav, target[j], kind))
                trades.append((date, dates[signal_index], tickers[j], delta[j], p[i, j],
                               notional[j], transaction[j], kind, False))
                costs.append((date, tickers[j], 'transaction', transaction[j], False))
        values = quantity * p[i]
        nav = float(cash + values.sum())
        if not np.isfinite(nav) or nav <= 0:
            raise ValueError(f'Nonpositive or nonfinite NAV at {date}')
        liquidation_cost = float(values.sum() * trading_cost)
        nav_rows.append((nav, cash, values[0], values[1], nav - liquidation_cost,
                         transaction.sum(), target_sh, signal_active,
                         quantity[0], quantity[1], p[i, 0], p[i, 1], liquidation_cost))
        for j, ticker in enumerate(tickers):
            positions.append((date, ticker, quantity[j], p[i, j], values[j], transaction[j]))
        previous_nav = nav
        previous_active = signal_active

    terminal_values = quantity * p[-1]
    for j in np.flatnonzero(quantity):
        fee = float(terminal_values[j] * trading_cost)
        trades.append((dates[-1], dates[-1], tickers[j], -quantity[j], p[-1, j],
                       -terminal_values[j], fee, 'liquidation', True))
        costs.append((dates[-1], tickers[j], 'liquidation', fee, True))
    nav_frame = pd.DataFrame(nav_rows, index=dates.copy(), columns=[
        'nav', 'cash', 'sgov_value', 'sh_value', 'liquidation_nav',
        'transaction_cost', 'target_sh', 'signal_active', 'sgov_quantity',
        'sh_quantity', 'sgov_price', 'sh_price', 'liquidation_cost',
    ])
    nav_frame.attrs['price_convention'] = 'adjusted-close synthetic units; distributions included'
    nav_frame.attrs['initial_execution'] = 'fractional initial-close diagnostic'
    return {
        'nav': nav_frame,
        'rejections': pd.DataFrame(rejections,columns=['date','signal_date','required_cash_after_fill','requested_active']),
        'trades': pd.DataFrame(trades, columns=[
            'date', 'signal_date', 'ticker', 'quantity', 'price', 'notional',
            'transaction_cost', 'kind', 'hypothetical',
        ]),
        'orders': pd.DataFrame(orders, columns=[
            'date', 'signal_date', 'ticker', 'quantity', 'reference_price',
            'reference_nav', 'target_notional', 'kind',
        ]),
        'daily_positions': pd.DataFrame(positions, columns=[
            'date', 'ticker', 'quantity', 'price', 'market_value', 'transaction_cost',
        ]),
        'costs': pd.DataFrame(costs, columns=['date', 'ticker', 'kind', 'amount', 'hypothetical']),
        'terminal_notional': float(terminal_values.sum()),
    }
