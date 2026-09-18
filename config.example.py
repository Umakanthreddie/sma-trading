"""
config.example.py — Template for config.py.

Copy this file to config.py and fill in your own News API key from
newsapi.org (free tier). config.py is gitignored so your real settings
never get committed to this repo.
"""

# ─────────────────────────────────────────────
# NEWS SOURCE
# "yahoo" (default) = free, no API key, no daily cap. "newsapi" or "both"
# use NEWS_API_KEY below (NewsAPI free tier caps at ~100 requests/day).
# ─────────────────────────────────────────────
NEWS_SOURCE = "yahoo"

# ─────────────────────────────────────────────
# NEWS API (NewsAPI.org — only used when NEWS_SOURCE is "newsapi" or "both")
# ─────────────────────────────────────────────
NEWS_API_KEY      = ""  # <-- put your newsapi.org key here
NEWS_MAX_ARTICLES = 10
NEWS_LANGUAGE     = "en"

# ─────────────────────────────────────────────
# AI PREDICTOR THRESHOLDS
# ─────────────────────────────────────────────
AI_BUY_THRESHOLD    = 65
AI_SELL_THRESHOLD   = 35
AI_WEIGHT_SMA       = 40
AI_WEIGHT_SENTIMENT = 35
AI_WEIGHT_MOMENTUM  = 25

# ─────────────────────────────────────────────
# BROKER SELECTION
# "paper"     → internal simulator (no broker/login needed) — ACTIVE
# "webull"    → Webull paper or live trading — currently broken (see above)
# "robinhood" → Robinhood (live only) — requires Robinhood credentials, unused
# ─────────────────────────────────────────────
BROKER = "paper"

# ─────────────────────────────────────────────
# WEBULL CREDENTIALS — unused while BROKER = "paper".
# ─────────────────────────────────────────────
WEBULL_PHONE       = ""
WEBULL_PASSWORD    = ""
WEBULL_TRADING_PIN = ""
WEBULL_DEVICE_ID   = "sma_trader_app"
WEBULL_PAPER       = True

# ─────────────────────────────────────────────
# ROBINHOOD CREDENTIALS — also intentionally left blank (unused).
# ─────────────────────────────────────────────
ROBINHOOD_USERNAME = ""
ROBINHOOD_PASSWORD = ""

# ─────────────────────────────────────────────
# PAPER-MODE FLAG (derived — do not hardcode)
# True whenever trades cannot touch real money, based on the actual
# broker routing logic in trader.py.
# ─────────────────────────────────────────────
PAPER_TRADING = (BROKER == "paper") or (BROKER == "webull" and WEBULL_PAPER)
PAPER_INITIAL_CAPITAL = 10_000.0

# ─────────────────────────────────────────────
# RISK MANAGEMENT GUARDRAILS
# ─────────────────────────────────────────────
MAX_POSITION_PCT   = 10.0   # Max % of portfolio per stock
MAX_OPEN_POSITIONS = 5      # Max simultaneous holdings
DAILY_LOSS_LIMIT   = 5.0    # Halt trading if down this % today
AI_MIN_SCORE       = 65     # Minimum AI score to place a BUY
STOP_LOSS_PCT      = 7.0    # Auto-sell if position drops this %

# ─────────────────────────────────────────────
# FULL MARKET SCANNER
# ─────────────────────────────────────────────
SCAN_SP500         = True    # ~503 stocks
SCAN_NASDAQ100     = True    # ~101 stocks
SCAN_NYSE_TOP      = True    # NYSE top 500
SCAN_RUSSELL2000   = False   # ~2000 small-caps (slow, off by default)
TOP_STOCKS_COUNT   = 50      # Top N to display after scoring
SCANNER_CACHE_HRS  = 6       # Hours to cache scan results

# ─────────────────────────────────────────────
# DYNAMIC WATCHLIST — auto-pick the traded tickers from the S&P 500 by
# momentum + news sentiment instead of a fixed list. See dynamic_watchlist.py.
# ─────────────────────────────────────────────
USE_DYNAMIC_WATCHLIST      = True
DYNAMIC_WATCHLIST_SIZE     = 15
DYNAMIC_WATCHLIST_POOL     = 25
DYNAMIC_WATCHLIST_CACHE_HRS = 12

# ─────────────────────────────────────────────
# AUTO_TRADE_WATCHLIST — fixed fallback, used only when
# USE_DYNAMIC_WATCHLIST = False or if the dynamic pick fails.
# ─────────────────────────────────────────────
AUTO_TRADE_WATCHLIST = [
    "AAPL", "TSLA", "GOOGL", "MSFT", "AMZN",
    "NVDA", "META", "AMD", "JPM", "V",
    "NFLX", "COIN", "PLTR", "SOFI", "RIVN",
]

# ─────────────────────────────────────────────
# WATCHLIST — the broad, ~100-stock list for manual scanning in the
# dashboard's "Manual Signals" tab. Diversified across sectors so you
# can scan for opportunities anywhere, not just tech/growth names.
# NOTE: scanning this whole list at once uses ~100 News-API requests
# in one click — on a free-tier key that's close to (or over) the
# daily quota, so expect sentiment scores to go neutral partway through
# a full scan once the quota is hit. It degrades gracefully, it just
# stops being "news-aware" for the rest of that run.
# ─────────────────────────────────────────────
WATCHLIST = [
    # Mega-cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "AVGO", "ORCL",
    "CRM", "ADBE", "AMD", "INTC", "CSCO", "IBM", "QCOM", "TXN",
    "INTU", "NOW", "UBER", "PANW", "SNOW", "SHOP", "PLTR", "COIN",
    # Communication / media
    "NFLX", "DIS", "CMCSA", "TMUS", "VZ", "T",
    # Consumer discretionary
    "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "BKNG", "TJX",
    "ABNB", "CMG", "RIVN", "SOFI",
    # Consumer staples
    "PG", "KO", "PEP", "WMT", "COST", "MDLZ", "CL", "KMB", "MO", "PM",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "BLK", "SCHW",
    "V", "MA", "PYPL",
    # Healthcare
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT",
    "DHR", "BMY", "AMGN", "GILD", "CVS", "ISRG",
    # Industrials
    "BA", "CAT", "GE", "HON", "UPS", "RTX", "LMT", "DE", "MMM", "UNP",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY",
    # Materials
    "LIN", "APD", "NEM",
    # Utilities
    "NEE", "DUK", "SO",
    # Real estate
    "AMT", "PLD",
]

# ─────────────────────────────────────────────
# STRATEGY PARAMETERS
# ─────────────────────────────────────────────
SMA_SHORT           = 20
SMA_LONG            = 50
MIN_SIGNAL_STRENGTH = 0.3
LOOKBACK_DAYS       = 365

# ─────────────────────────────────────────────
# ALERT SETTINGS
# ─────────────────────────────────────────────
CONSOLE_ALERTS = True
EMAIL_ALERTS   = False
EMAIL_SENDER   = ""
EMAIL_PASSWORD = ""
EMAIL_RECEIVER = ""
SMTP_SERVER    = "smtp.gmail.com"
SMTP_PORT      = 587

# ─────────────────────────────────────────────
# OUTPUT SETTINGS
# ─────────────────────────────────────────────
CHARTS_DIR     = "charts"
DATA_CACHE_DIR = "cache"
