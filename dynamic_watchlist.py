"""
dynamic_watchlist.py — Builds the auto-trade watchlist dynamically instead
of trading the same fixed tickers every run.

Two-stage selection, kept cheap on news-API usage:

  Stage 1 (momentum, free): every S&P 500 stock is scored on price/volume
  momentum using yfinance price data only — no news calls, so this is free
  regardless of NEWS_SOURCE.

  Stage 2 (sentiment, cheap): news sentiment is checked on just the top
  DYNAMIC_WATCHLIST_POOL stocks from stage 1 (a small pool, e.g. 25), not
  the full 503. That keeps news usage bounded even when NEWS_SOURCE is
  "newsapi" or "both".

  The final picks are the best DYNAMIC_WATCHLIST_SIZE stocks by a combined
  score: 60% momentum + 40% news sentiment.

Results are cached to disk (data/dynamic_watchlist_cache.json) for
DYNAMIC_WATCHLIST_CACHE_HRS hours, so scheduled runs every 30 minutes reuse
the same picks instead of rescanning the S&P 500 and re-spending news calls
on every run.
"""

import os
import json
from datetime import datetime

import config
import stock_scanner
import news_analyzer

CACHE_FILE = os.path.join(config.DATA_CACHE_DIR, "dynamic_watchlist_cache.json")


# ─────────────────────────────────────────────
# Cache helpers
# ─────────────────────────────────────────────
def _cache_valid() -> bool:
    if not os.path.exists(CACHE_FILE):
        return False
    age_hrs = (datetime.now().timestamp() - os.path.getmtime(CACHE_FILE)) / 3600
    return age_hrs < getattr(config, "DYNAMIC_WATCHLIST_CACHE_HRS", 12)


def _load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(data: dict):
    os.makedirs(config.DATA_CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────
# Stage 1 — momentum scan, S&P 500 only, no news calls
# ─────────────────────────────────────────────
def _momentum_pool(pool_size: int) -> list:
    """Score every S&P 500 stock on price/volume momentum, return the top N."""
    tickers = stock_scanner.get_sp500_tickers()
    results = []
    for t in tickers:
        r = stock_scanner._score_ticker(t)
        if r:
            results.append(r)
    results.sort(key=lambda r: r["Score"], reverse=True)
    return results[:pool_size]


# ─────────────────────────────────────────────
# Stage 2 — news sentiment on the pool, then combine
# ─────────────────────────────────────────────
def build_watchlist(force_refresh: bool = False) -> dict:
    """
    Returns:
        {
          "tickers":     [str, ...],   # final picks, best first
          "detail":      [ {ticker, momentum_score, sentiment_score,
                             sentiment_label, article_count, combined_score}, ... ],
          "pool_detail": same shape, for the whole momentum pool (not just picks),
          "built_at":    ISO timestamp string,
        }
    """
    if not force_refresh and _cache_valid():
        cached = _load_cache()
        if cached and cached.get("tickers"):
            return cached

    pool_size = getattr(config, "DYNAMIC_WATCHLIST_POOL", 25)
    top_n     = getattr(config, "DYNAMIC_WATCHLIST_SIZE", 15)

    pool = _momentum_pool(pool_size)
    pool_tickers = [r["Ticker"] for r in pool]

    news_dict = news_analyzer.analyze_multiple(pool_tickers) if pool_tickers else {}

    detail = []
    for r in pool:
        tk = r["Ticker"]
        news = news_dict.get(tk, {})
        sentiment_score = news.get("sentiment_score", 0.0)        # -1..+1
        sentiment_0_100 = (sentiment_score + 1) * 50               # 0..100
        combined = round(0.6 * r["Score"] + 0.4 * sentiment_0_100, 1)
        detail.append({
            "ticker":           tk,
            "momentum_score":   r["Score"],
            "sentiment_score":  sentiment_score,
            "sentiment_label":  news.get("sentiment_label", "Neutral ➡️"),
            "article_count":    news.get("article_count", 0),
            "combined_score":   combined,
        })

    detail.sort(key=lambda d: d["combined_score"], reverse=True)
    picks = detail[:top_n]

    result = {
        "tickers":     [d["ticker"] for d in picks],
        "detail":      picks,
        "pool_detail": detail,
        "built_at":    datetime.now().isoformat(timespec="seconds"),
    }

    if result["tickers"]:
        _save_cache(result)
    return result


def get_watchlist_tickers() -> list:
    """Convenience: just the ticker list, using the cache when fresh, with a
    static fallback if the dynamic pick fails or returns nothing."""
    try:
        data = build_watchlist()
        if data.get("tickers"):
            return data["tickers"]
    except Exception:
        pass
    return list(getattr(config, "AUTO_TRADE_WATCHLIST", config.WATCHLIST[:15]))
