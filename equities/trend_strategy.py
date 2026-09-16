"""
Nasdaq Long-Term Trend Strategy V2
==================================

Purpose
-------
A slower, lower-turnover Nasdaq-100 trend-following strategy designed for
QQQ / broad index exposure rather than high-volatility crypto-style trading.

Core idea
---------
1. Only participate when QQQ is above its 200-day EMA.
2. Initial entry on a fresh 55-day breakout.
3. After an exit, allow re-entry when price recovers back above the 50-day EMA
   while still above the 200-day EMA.
4. Ignore ordinary short-term pullbacks.
5. Exit only after THREE consecutive daily closes below the 100-day EMA.
6. Keep a 10% fixed hard stop as an emergency risk control.
7. Compare directly with QQQ Buy & Hold using the same starting capital and
   explicit commission/slippage assumptions.

This is a research/backtesting script, not investment advice.

Install:
    pip install backtrader yfinance pandas numpy matplotlib

Run:
    python nasdaq_trend_strategy_v2.py
    python nasdaq_trend_strategy_v2.py --ticker QQQ --start 2015-01-01 --end 2026-01-01
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import backtrader as bt
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf


@dataclass
class ResearchConfig:
        ticker: str = "QQQ"
        start: str = "2015-01-01"
        end: str = "2026-01-01"
        initial_cash: float = 100_000.0
        commission: float = 0.0002
        slippage: float = 0.0003

        breakout_period: int = 55

        # EMA50: only for re-entry
        ema_reentry: int = 50

        # EMA100: main trend exit
        ema_exit: int = 100

        # EMA200: long-term regime
        ema_regime: int = 200

        exit_confirm_days: int = 3

        hard_stop: float = 0.10
        invest_pct: float = 0.98
        allow_reentry: bool = True
        printlog: bool = False


def download_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    start_dt = pd.Timestamp(start)
    warmup_start = (start_dt - pd.Timedelta(days=500)).strftime("%Y-%m-%d")

    print(f"Downloading {ticker}: {warmup_start} -> {end}")

    df = yf.download(
        ticker,
        start=warmup_start,
        end=end,
        auto_adjust=True,
        progress=False,
        actions=False,
    )

    if df.empty:
        raise RuntimeError(f"No data returned for {ticker}.")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing columns: {missing}")

    df = df[required].dropna().copy()

    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)

    return df


class NasdaqLongTermTrendV2(bt.Strategy):
    params = dict(
        trade_start=None,

        breakout_period=55,

        ema_reentry=50,
        ema_exit=100,
        ema_regime=200,

        exit_confirm_days=3,

        hard_stop=0.10,
        invest_pct=0.98,
        allow_reentry=True,

        printlog=False,
    )

    def __init__(self):
        # EMA50: re-entry
        self.ema50 = bt.ind.EMA(
            self.data.close,
            period=self.p.ema_reentry
        )

        # EMA100: main trend exit
        self.ema100 = bt.ind.EMA(
            self.data.close,
            period=self.p.ema_exit
        )

        # EMA200: long-term bull regime
        self.ema200 = bt.ind.EMA(
            self.data.close,
            period=self.p.ema_regime
)
        self.highest = bt.ind.Highest(self.data.high, period=self.p.breakout_period)

        self.order = None
        self.entry_price = None
        self.entry_date = None
        self.entry_size = None
        self.entry_tag = None
        self.pending_entry_tag = None
        self.pending_exit_tag = None
        self.below_ema_count = 0
        self.has_exited_before = False

        self.equity_curve = []
        self.trade_records = []

    def log(self, text: str) -> None:
        if self.p.printlog:
            dt = self.data.datetime.date(0)
            print(f"{dt.isoformat()} | {text}")

    def after_trade_start(self) -> bool:
        if self.p.trade_start is None:
            return True
        return self.data.datetime.datetime(0) >= self.p.trade_start

    def bull_regime(self) -> bool:
        # Deliberately simple for an index: price must be above EMA200.
        return self.data.close[0] > self.ema200[0]

    def fresh_55d_breakout(self) -> bool:
        if len(self) < self.p.breakout_period + 2:
            return False

        prior_high = self.highest[-1]
        prior_prior_high = self.highest[-2]

        return (
            self.data.close[0] > prior_high
            and self.data.close[-1] <= prior_prior_high
        )

    def initial_entry_signal(self) -> bool:
        return self.bull_regime() and self.fresh_55d_breakout()

    def reentry_signal(self) -> bool:
        # Re-entry is only a trend-recovery mechanism now.
        if not self.p.allow_reentry:
            return False
        if not self.has_exited_before:
            return False
        if not self.bull_regime():
            return False
        if len(self) < 2:
            return False

        return (
            self.data.close[0] > self.ema50[0]
            and self.data.close[-1] <= self.ema50[-1]
        )

    def calculate_size(self) -> int:
        cash = float(self.broker.getcash())
        price = float(self.data.close[0])
        if cash <= 0 or price <= 0:
            return 0
        return max(math.floor(cash * self.p.invest_pct / price), 0)

    def next(self):
        current_dt = self.data.datetime.datetime(0)

        if self.p.trade_start is None or current_dt >= self.p.trade_start:
            self.equity_curve.append(
                {
                    "date": pd.Timestamp(current_dt.date()),
                    "value": float(self.broker.getvalue()),
                }
            )

        if not self.after_trade_start():
            return

        if self.order:
            return

        # ========================================================
        # No position: look for entry
        # ========================================================
        if not self.position:
            self.below_ema_count = 0

            # Initial entry: 55-day breakout
            if self.initial_entry_signal():
                size = self.calculate_size()

                if size > 0:
                    self.pending_entry_tag = "55d_breakout"

                    self.log(
                        f"BUY initial breakout | "
                        f"close={self.data.close[0]:.2f}"
                    )

                    self.order = self.buy(size=size)

                return

            # Re-entry: recover above EMA50
            if self.reentry_signal():
                size = self.calculate_size()

                if size > 0:
                    self.pending_entry_tag = "ema50_reentry"

                    self.log(
                        f"BUY trend recovery | "
                        f"close={self.data.close[0]:.2f}"
                    )

                    self.order = self.buy(size=size)

                return

        # ========================================================
        # Have position: manage exit
        # ========================================================
        else:

            # ----------------------------------------------------
            # Emergency fixed hard stop
            # ----------------------------------------------------
            if (
                self.entry_price is not None
                and self.data.close[0]
                <= self.entry_price * (1.0 - self.p.hard_stop)
            ):
                self.pending_exit_tag = "hard_stop"

                self.log(
                    f"SELL hard stop | "
                    f"close={self.data.close[0]:.2f}"
                )

                self.order = self.close()
                return

            # ----------------------------------------------------
            # Long-term trend exit:
            # consecutive closes below EMA100
            # ----------------------------------------------------
            if self.data.close[0] < self.ema100[0]:
                self.below_ema_count += 1
            else:
                self.below_ema_count = 0

            if self.below_ema_count >= self.p.exit_confirm_days:
                self.pending_exit_tag = (
                    f"ema100_{self.p.exit_confirm_days}d_failed"
                )

                self.log(
                    f"SELL trend failure | "
                    f"close={self.data.close[0]:.2f}"
                )

                self.order = self.close()
                return

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            if order.isbuy():
                self.entry_price = float(order.executed.price)
                self.entry_date = pd.Timestamp(self.data.datetime.date(0))
                self.entry_size = abs(int(order.executed.size))
                self.entry_tag = self.pending_entry_tag
                self.pending_entry_tag = None
                self.below_ema_count = 0
                self.log(
                    f"BUY FILLED | price={order.executed.price:.2f}, "
                    f"size={order.executed.size}"
                )
            else:
                self.log(f"SELL FILLED | price={order.executed.price:.2f}")
                self.has_exited_before = True
                self.below_ema_count = 0

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"ORDER FAILED | status={order.getstatusname()}")

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        exit_date = pd.Timestamp(self.data.datetime.date(0))

        if (
            self.entry_price is not None
            and self.entry_size is not None
            and self.entry_price > 0
            and self.entry_size > 0
        ):
            entry_notional = self.entry_price * self.entry_size
            return_pct = float(trade.pnlcomm) / entry_notional * 100.0
        else:
            return_pct = np.nan

        holding_days = (
            (exit_date - self.entry_date).days
            if self.entry_date is not None
            else np.nan
        )

        self.trade_records.append(
            {
                "entry_date": self.entry_date,
                "exit_date": exit_date,
                "entry_tag": self.entry_tag,
                "exit_tag": self.pending_exit_tag,
                "entry_price": self.entry_price,
                "size": self.entry_size,
                "holding_days": holding_days,
                "pnl_before_costs": float(trade.pnl),
                "pnl_after_costs": float(trade.pnlcomm),
                "return_pct": return_pct,
            }
        )

        self.entry_price = None
        self.entry_date = None
        self.entry_size = None
        self.entry_tag = None
        self.pending_exit_tag = None


def calculate_metrics(
    equity: pd.Series,
    initial_cash: float,
    periods_per_year: int = 252,
) -> dict:
    equity = equity.dropna()
    if len(equity) < 2:
        return {}

    daily_returns = equity.pct_change().dropna()
    total_return = equity.iloc[-1] / initial_cash - 1.0

    days = max((equity.index[-1] - equity.index[0]).days, 1)
    years = days / 365.25
    cagr = (equity.iloc[-1] / initial_cash) ** (1.0 / years) - 1.0

    rolling_peak = equity.cummax()
    drawdown = equity / rolling_peak - 1.0
    max_drawdown = drawdown.min()

    sharpe = np.nan
    if len(daily_returns) > 1 and daily_returns.std(ddof=1) > 0:
        sharpe = (
            daily_returns.mean()
            / daily_returns.std(ddof=1)
            * np.sqrt(periods_per_year)
        )

    downside = daily_returns[daily_returns < 0]
    sortino = np.nan
    if len(downside) > 1 and downside.std(ddof=1) > 0:
        sortino = (
            daily_returns.mean()
            / downside.std(ddof=1)
            * np.sqrt(periods_per_year)
        )

    calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else np.nan

    return {
        "Final Value": equity.iloc[-1],
        "Total Return %": total_return * 100.0,
        "CAGR %": cagr * 100.0,
        "Max Drawdown %": max_drawdown * 100.0,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Calmar": calmar,
    }


def make_buy_and_hold_equity(
    close: pd.Series,
    initial_cash: float,
    one_way_cost: float,
) -> pd.Series:
    close = close.dropna().copy()
    if close.empty:
        return pd.Series(dtype=float)

    entry_price = float(close.iloc[0])
    investable_cash = initial_cash * (1.0 - one_way_cost)
    equity = investable_cash * close / entry_price
    equity.iloc[-1] *= 1.0 - one_way_cost
    return equity


def run_backtest(config: ResearchConfig):
    df = download_data(config.ticker, config.start, config.end)
    trade_start = datetime.strptime(config.start, "%Y-%m-%d")

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.adddata(bt.feeds.PandasData(dataname=df))
    cerebro.addstrategy(
        NasdaqLongTermTrendV2,
        trade_start=trade_start,
        breakout_period=config.breakout_period,
        ema_exit=config.ema_exit,
        ema_regime=config.ema_regime,
        exit_confirm_days=config.exit_confirm_days,
        hard_stop=config.hard_stop,
        invest_pct=config.invest_pct,
        allow_reentry=config.allow_reentry,
        printlog=config.printlog,
        ema_reentry=config.ema_reentry,
    )

    cerebro.broker.setcash(config.initial_cash)
    cerebro.broker.setcommission(commission=config.commission)

    slippage_applied = False
    try:
        cerebro.broker.set_slippage_perc(
            perc=config.slippage,
            slip_open=True,
            slip_limit=True,
            slip_match=True,
            slip_out=False,
        )
        slippage_applied = True
    except Exception:
        print(
            "Warning: Backtrader slippage model could not be enabled. "
            "Commission is still applied."
        )

    results = cerebro.run()
    strat = results[0]

    equity_df = pd.DataFrame(strat.equity_curve)
    if equity_df.empty:
        raise RuntimeError("No strategy equity observations were recorded.")

    equity_df = (
        equity_df.drop_duplicates(subset="date", keep="last")
        .set_index("date")
        .sort_index()
    )
    strategy_equity = equity_df["value"].rename("Strategy")

    research_prices = df.loc[pd.Timestamp(config.start):].copy()
    if research_prices.empty:
        raise RuntimeError("No benchmark data inside requested research period.")

    one_way_cost = config.commission + (
        config.slippage if slippage_applied else 0.0
    )

    benchmark_equity = make_buy_and_hold_equity(
        research_prices["Close"],
        config.initial_cash,
        one_way_cost,
    ).rename("Buy & Hold")

    combined = pd.concat(
        [strategy_equity, benchmark_equity],
        axis=1,
    ).dropna()

    strategy_metrics = calculate_metrics(combined["Strategy"], config.initial_cash)
    benchmark_metrics = calculate_metrics(combined["Buy & Hold"], config.initial_cash)

    comparison = pd.DataFrame(
        {
            "Trend Strategy V2": strategy_metrics,
            "Buy & Hold": benchmark_metrics,
        }
    )

    trades = pd.DataFrame(strat.trade_records)

    output_dir = Path("nasdaq_results_v2")
    output_dir.mkdir(exist_ok=True)

    combined.to_csv(output_dir / f"{config.ticker}_equity_curve.csv")
    trades.to_csv(output_dir / f"{config.ticker}_trades.csv", index=False)
    comparison.to_csv(output_dir / f"{config.ticker}_metrics.csv")

    normalized = combined / config.initial_cash
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(normalized.index, normalized["Strategy"], label="Trend Strategy V2")
    ax.plot(
        normalized.index,
        normalized["Buy & Hold"],
        label=f"{config.ticker} Buy & Hold",
    )
    ax.set_title(f"{config.ticker}: Long-Term Trend V2 vs Buy & Hold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Growth of $1")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / f"{config.ticker}_comparison.png", dpi=160)
    plt.close(fig)

    print()
    print("=" * 76)
    print(f"NASDAQ LONG-TERM TREND V2 — {config.ticker}")
    print("=" * 76)
    print(f"Research period: {config.start} -> {config.end}")
    print(f"Initial cash:    ${config.initial_cash:,.2f}")
    print(
        "One-way costs:  "
        f"commission={config.commission:.4%}, "
        f"slippage={config.slippage:.4%}"
    )
    print()
    print(comparison.round(3).to_string())

    print()
    print("-" * 76)
    print("Trade diagnostics")
    print("-" * 76)

    if trades.empty:
        print("No closed trades.")
    else:
        print(f"Closed trades: {len(trades)}")
        print(f"Average holding days: {trades['holding_days'].mean():.1f}")
        print(f"Median holding days:  {trades['holding_days'].median():.1f}")
        print(f"Max holding days:     {trades['holding_days'].max():.0f}")

        print()
        print("By entry tag:")
        entry_stats = (
            trades.groupby("entry_tag", dropna=False)
            .agg(
                trades=("pnl_after_costs", "size"),
                avg_pnl=("pnl_after_costs", "mean"),
                total_pnl=("pnl_after_costs", "sum"),
                avg_return_pct=("return_pct", "mean"),
                win_rate=("pnl_after_costs", lambda x: (x > 0).mean() * 100.0),
                avg_holding_days=("holding_days", "mean"),
            )
        )
        print(entry_stats.round(3).to_string())

        print()
        print("By exit tag:")
        exit_stats = (
            trades.groupby("exit_tag", dropna=False)
            .agg(
                trades=("pnl_after_costs", "size"),
                avg_pnl=("pnl_after_costs", "mean"),
                total_pnl=("pnl_after_costs", "sum"),
                avg_return_pct=("return_pct", "mean"),
                win_rate=("pnl_after_costs", lambda x: (x > 0).mean() * 100.0),
                avg_holding_days=("holding_days", "mean"),
            )
        )
        print(exit_stats.round(3).to_string())

    print()
    print("Files written to:")
    print(f"  {output_dir.resolve()}")
    print("=" * 76)

    return comparison, combined, trades


def parse_args():
    parser = argparse.ArgumentParser(
        description="Nasdaq long-term trend V2 research backtest"
    )
    parser.add_argument("--ticker", default="QQQ")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--cash", type=float, default=100_000.0)
    parser.add_argument("--commission", type=float, default=0.0002)
    parser.add_argument("--slippage", type=float, default=0.0003)
    parser.add_argument(
        "--no-reentry",
        action="store_true",
        help="Disable EMA50 recovery re-entry.",
    )
    parser.add_argument("--printlog", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    config = ResearchConfig(
        ticker=args.ticker.upper(),
        start=args.start,
        end=args.end,
        initial_cash=args.cash,
        commission=args.commission,
        slippage=args.slippage,
        allow_reentry=not args.no_reentry,
        printlog=args.printlog,
    )

    run_backtest(config)
