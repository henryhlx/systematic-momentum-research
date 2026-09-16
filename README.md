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

The fixed trend-following framework did not consistently outperform passive
buy-and-hold investing.

It reduced maximum drawdown on QQQ, MSFT and NVDA, but reduced market exposure
also created a substantial opportunity cost during strong bull markets.

The results suggest that trend following may be more useful as a
risk-management overlay than as a universal source of excess returns in
large-cap equities.

The research also indicated that different asset classes require different
time horizons. Higher-volatility cryptocurrency markets supported faster
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