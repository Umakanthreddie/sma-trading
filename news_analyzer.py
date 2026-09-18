"""
news_analyzer.py — Fetch and analyze news sentiment for stocks.

Uses:
  - NewsAPI to fetch recent headlines
  - VADER Sentiment to score each headline (-1.0 to +1.0)
"""

from datetime import datetime, timedelta

import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import config

_analyzer = SentimentIntensityAnalyzer()


# ─────────────────────────────────────────────
# Fetch headlines from NewsAPI
# ─────────────────────────────────────────────
def fetch_news(ticker: str, company_name: str = "") -> list:
    """
    Fetch recent news headlines for a stock ticker.

    Args:
        ticker:       Stock symbol (e.g. "AAPL")
        company_name: Optional company name for better results (e.g. "Apple")

    Returns:
        List of article dicts with: title, description, url, publishedAt, source
    """
    query = company_name if company_name else ticker
    from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    params = {
        "q":        f"{query} stock",
        "from":     from_date,
        "language": config.NEWS_LANGUAGE,
        "sortBy":   "publishedAt",
        "pageSize": config.NEWS_MAX_ARTICLES,
        "apiKey":   config.NEWS_API_KEY,
    }

    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params=params,
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != "ok":
            return []
        return data.get("articles", [])
    except Exception:
        return []


# ─────────────────────────────────────────────
# Score a single headline
# ─────────────────────────────────────────────
def score_headline(text: str) -> float:
    """
    Score a headline using VADER sentiment analysis.

    Returns:
        Compound score from -1.0 (very negative) to +1.0 (very positive)
    """
    if not text:
        return 0.0
    scores = _analyzer.polarity_scores(text)
    return round(scores["compound"], 4)


# ─────────────────────────────────────────────
# Analyze all headlines for a ticker
# ─────────────────────────────────────────────
def analyze(ticker: str, company_name: str = "") -> dict:
    """
    Fetch and analyze news for a ticker.

    Returns:
        {
          ticker:          str,
          sentiment_score: float   (-1 to +1, weighted average),
          sentiment_label: str     ("Very Bullish" | "Bullish" | "Neutral" | "Bearish" | "Very Bearish"),
          articles:        list of {title, source, url, published, score},
          article_count:   int,
        }
    """
    articles = fetch_news(ticker, company_name)

    scored = []
    for art in articles:
        title = art.get("title") or ""
        desc  = art.get("description") or ""
        text  = f"{title}. {desc}"
        score = score_headline(text)
        scored.append({
            "title":     title[:120] + "..." if len(title) > 120 else title,
            "source":    art.get("source", {}).get("name", "Unknown"),
            "url":       art.get("url", ""),
            "published": art.get("publishedAt", "")[:10],
            "score":     score,
        })

    # Weighted average: more recent articles count more
    if scored:
        weights = list(range(len(scored), 0, -1))   # [N, N-1, ..., 1]
        weighted_sum = sum(a["score"] * w for a, w in zip(scored, weights))
        total_weight = sum(weights)
        avg_score    = round(weighted_sum / total_weight, 4)
    else:
        avg_score = 0.0

    # Label
    if avg_score >= 0.35:
        label = "Very Bullish 🚀"
    elif avg_score >= 0.10:
        label = "Bullish 📈"
    elif avg_score <= -0.35:
        label = "Very Bearish 💣"
    elif avg_score <= -0.10:
        label = "Bearish 📉"
    else:
        label = "Neutral ➡️"

    return {
        "ticker":          ticker,
        "sentiment_score": avg_score,
        "sentiment_label": label,
        "articles":        scored,
        "article_count":   len(scored),
    }


def analyze_multiple(tickers: list, name_map: dict = None) -> dict:
    """
    Analyze news for multiple tickers.

    Args:
        tickers:  List of ticker symbols
        name_map: Optional dict mapping ticker -> company name

    Returns:
        Dict of {ticker: analysis_result}
    """
    name_map = name_map or {}
    results  = {}
    for ticker in tickers:
        company = name_map.get(ticker, "")
        results[ticker] = analyze(ticker, company)
    return results
