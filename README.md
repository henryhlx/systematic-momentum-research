# Systematic Momentum and Trend Research

Independent research project examining how systematic momentum and
trend-following strategies behave across cryptocurrencies, the Nasdaq-100,
and selected large-cap US equities.

The project focuses on research methodology rather than maximising historical
backtest returns. It includes transaction costs, slippage, benchmark
comparisons, out-of-sample testing and signal diagnostics.

## Assets Studied

### Cryptocurrency
- BTC/USDT
- ETH/USDT

### Equity Index
- QQQ

### Individual Equities
- AAPL
- MSFT
- NVDA

## Crypto Strategy

The cryptocurrency component uses a long-only momentum strategy on BTC/USDT
and ETH/USDT, implemented and tested using Freqtrade.

The strategy operates primarily on 1-hour candles and is designed to participate
in persistent directional moves while avoiding weaker breakout signals.

### Entry Logic

The primary entry signal is a breakout above the recent 20-hour price range.

Breakout signals are combined with trend, momentum and liquidity filters,
including:

- Short- and medium-term exponential moving averages
- RSI-based momentum confirmation
- Relative trading-volume filters
- Additional trend-strength filters where applicable

The purpose of these filters is to reduce entries during weak or low-volume
breakouts rather than to maximise the number of trades.

### Re-entry Logic

A separate re-entry condition is used after the strategy has exited a position.

This allows the system to re-establish exposure when momentum resumes after
a temporary correction, without requiring a completely new breakout cycle.

Re-entry conditions use their own momentum and volume thresholds and were
evaluated separately from the initial breakout signal.

### Exit and Risk Management

The main trend exit is triggered when price remains below the short-term
EMA for several consecutive hourly candles, indicating that momentum has
persistently weakened rather than merely experiencing a short pullback.

The strategy also uses:

- A fixed emergency stop-loss
- A maximum number of simultaneous positions
- Spot trading only, without leverage
- Exchange trading fees in backtesting

The primary signal timeframe is 1 hour. A 5-minute detail timeframe was also
used in later backtests to improve the simulation of intra-candle trade
execution.

### Validation Approach

The strategy was not evaluated using a single full-period optimisation.

2020 was used during strategy development, while the main evaluation focuses
on the 2021–2025 out-of-sample period.

Lookahead-bias and recursive-indicator checks were also performed before the
out-of-sample results were interpreted.

## Crypto Out-of-Sample Results

The cryptocurrency strategy was developed using 2020 data. Therefore, 2020 is treated as a development sample rather than a true out-of-sample period.

The main out-of-sample evaluation covers 2021–2025.

| Year | Sample | Return | Trades | Avg / Trade | Win Rate | Sharpe | Wallet Max DD | Market Change |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2020 | Development | +114.19% | 108 | +1.53% | 45.4% | 2.38 | — | +386.8% |
| 2021 | OOS | +56.08% | 100 | +0.96% | 39.0% | 1.68 | 11.21% | +234.0% |
| 2022 | OOS | +4.43% | 27 | +0.35% | 48.1% | 0.54 | 7.30% | -66.3% |
| 2023 | OOS | +11.09% | 77 | +0.35% | 36.4% | 0.61 | 16.40% | +121.5% |
| 2024 | OOS | +14.88% | 82 | +0.38% | 45.1% | 0.81 | 17.14% | +84.4% |
| 2025 | OOS | +35.84% | 57 | +1.18% | 36.8% | 1.76 | 7.65% | -9.2% |


## Equity Strategy

The final fixed equity trend framework uses:

- 200-day EMA as the long-term regime filter
- 55-day breakout for initial entry
- 50-day EMA recovery for re-entry
- Three consecutive closes below the 100-day EMA for exit
- Emergency hard stop
- Explicit commission and slippage assumptions

## Final Equity Results

Backtest period: 2015-01-01 to 2026-01-01.

| Asset | Strategy CAGR | Buy & Hold CAGR | Strategy Max DD | Buy & Hold Max DD | Strategy Sharpe | Buy & Hold Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| QQQ | 12.82% | 18.52% | -25.48% | -35.12% | 0.853 | 0.885 |
| AAPL | 12.74% | 24.58% | -39.03% | -38.52% | 0.665 | 0.908 |
| MSFT | 15.71% | 25.47% | -28.76% | -37.15% | 0.805 | 0.980 |
| NVDA | 55.57% | 71.88% | -51.09% | -66.34% | 1.319 | 1.357 |


## Key Findings

### Cryptocurrency

The crypto momentum strategy remained profitable across the 2021–2025
out-of-sample period, including during the severe 2022 market decline.
However, performance and Sharpe ratios varied substantially across regimes.

### Equity Index and Individual Stocks

The fixed trend-following framework did not consistently outperform passive
buy-and-hold investing.

It reduced maximum drawdown on QQQ, MSFT and NVDA, but reduced market exposure
also created a substantial opportunity cost during strong bull markets.

### Cross-Asset Observation

The research suggests that strategy time horizons should depend on the
underlying asset. Higher-volatility cryptocurrency markets supported faster
momentum signals, while the Nasdaq-100 benefited from slower exits and longer
holding periods.

## Repository Structure

```text
crypto/
    MomentumStrategy.py

equities/
    trend_strategy.py
```

## Running the Equity Backtest

Install dependencies:

pip install -r requirements.txt

Example:

python equities/trend_strategy.py \
    --ticker QQQ \
    --start 2015-01-01 \
    --end 2026-01-01

The script downloads adjusted historical equity data using yfinance.

### Windows PowerShell

```powershell
python .\equities\trend_strategy.py `
  --ticker QQQ `
  --start 2015-01-01 `
  --end 2026-01-01
```  

## Limitations

This is a research/backtesting project, not a live trading system.

Limitations include historical-data quality, execution-model assumptions,
a small individual-equity sample, possible survivorship bias, and the fact
that historical backtest performance does not imply future performance.

## Technologies

Python, pandas, NumPy, Backtrader, Freqtrade, Docker, Git and GitHub.

## Author

Linxuan Hu
University of Edinburgh
GitHub: https://github.com/henryhlx