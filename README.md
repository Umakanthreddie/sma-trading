# 📈 SMA Crossover Trading Strategy

A Python tool that scans stocks for **Golden Cross / Death Cross** signals using the Simple Moving Average (SMA) Crossover strategy.

> ⚠️ **Disclaimer**: This tool is for educational purposes only. It does **not** constitute financial advice. Always do your own research before making any investment decisions.

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run a scan (default)
```bash
python main.py
```

### 3. Run a backtest
```bash
python main.py --backtest
```

### 4. Generate a chart for a specific stock
```bash
python main.py --plot AAPL
```

### 5. Generate charts for all stocks
```bash
python main.py --plot-all
```

### 6. Add extra tickers for one session
```bash
python main.py --scan --add COIN HOOD PLTR
```

---

## 📊 Strategy Explained

| Signal | Condition | Meaning |
|--------|-----------|---------|
| 🟢 **BUY** | SMA-20 crosses **above** SMA-50 | Golden Cross — bullish momentum |
| 🔴 **SELL** | SMA-20 crosses **below** SMA-50 | Death Cross — bearish momentum |
| 🟡 **HOLD** | No crossover detected today | Maintain current position |

---

## ⚙️ Configuration (`config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `WATCHLIST` | `["AAPL", "TSLA", ...]` | Stocks to scan |
| `SMA_SHORT` | `20` | Short-term MA period (days) |
| `SMA_LONG` | `50` | Long-term MA period (days) |
| `MIN_SIGNAL_STRENGTH` | `0.3` | Min % MA gap to confirm a signal |
| `LOOKBACK_DAYS` | `365` | Historical data window |
| `EMAIL_ALERTS` | `False` | Enable email alerts |

---

## 📁 Project Structure

```
sma-trader/
├── main.py          # Entry point — CLI commands
├── config.py        # Watchlist & strategy settings
├── strategy.py      # SMA crossover logic
├── data_fetcher.py  # yfinance data download + caching
├── alerts.py        # Console & email alerts
├── backtester.py    # Historical backtest simulation
├── plotter.py       # Chart generation (matplotlib)
├── requirements.txt # Python dependencies
├── charts/          # Generated chart images (auto-created)
└── cache/           # Cached stock data (auto-created)
```

---

## 📧 Email Alerts Setup

1. Open `config.py`
2. Set `EMAIL_ALERTS = True`
3. Fill in `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECEIVER`
4. Use a [Gmail App Password](https://support.google.com/accounts/answer/185833) (not your regular password)

---

## 🛠️ CLI Reference

```
python main.py [OPTIONS]

Options:
  --scan            Scan watchlist for buy/sell signals (default)
  --backtest        Run strategy backtest on watchlist
  --plot TICKER     Generate chart for a specific ticker
  --plot-all        Generate charts for all watchlist tickers
  --add T1 T2 ...   Add extra tickers to watchlist (session only)
  -h, --help        Show help message
```
