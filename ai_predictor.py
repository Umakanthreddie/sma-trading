"""
ai_predictor.py — Combines SMA signals + News Sentiment + Momentum
into a single AI Confidence Score (0–100) with BUY/SELL/HOLD recommendation.

Score breakdown:
  SMA Crossover (40%)  — technical trend signal
  News Sentiment (35%) — market sentiment from headlines
  Price Momentum (25%) — recent price + volume performance
"""

import numpy as np
import pandas as pd

import config
import strategy
import news_analyzer


# ─────────────────────────────────────────────
# Individual component scorers
# ─────────────────────────────────────────────

def _sma_score(df: pd.DataFrame,
               short: int = config.SMA_SHORT,
               long:  int = config.SMA_LONG) -> float:
    """
    Score the SMA technical signal (0–100).
    70–100 = bullish crossover or strong uptrend
    30–70  = neutral (above/below but no crossover)
    0–30   = bearish crossover or strong downtrend
    """
    df = strategy.detect_signals(df, short, long)
    short_col = f"SMA_{short}"
    long_col  = f"SMA_{long}"
    df = df.dropna(subset=[short_col, long_col])
    if df.empty:
        return 50.0

    last = df.iloc[-1]
    sig  = last["Signal"]
    pos  = last["Position"]
    gap  = float(last["Signal_Strength"])

    if sig == "BUY":
        return min(95, 75 + gap * 5)
    elif sig == "SELL":
        return max(5, 25 - gap * 5)
    else:
        # HOLD — score based on which side the price is on
        if pos == 1:
            return min(70, 55 + gap * 2)   # Above long MA = mildly bullish
        elif pos == -1:
            return max(30, 45 - gap * 2)   # Below long MA = mildly bearish
        return 50.0


def _sentiment_score(sentiment_value: float) -> float:
    """
    Convert VADER compound score (-1 to +1) to 0–100 scale.
    """
    # Linear map: -1 → 0, 0 → 50, +1 → 100
    return round((sentiment_value + 1) / 2 * 100, 1)


def _momentum_score(df: pd.DataFrame) -> float:
    """
    Score recent price + volume momentum (0–100).
    """
    try:
        close  = df["Close"].squeeze()
        volume = df["Volume"].squeeze()

        if len(close) < 10:
            return 50.0

        # 5-day and 20-day returns
        ret_5d  = float((close.iloc[-1] - close.iloc[-6])  / close.iloc[-6]  * 100) if len(close) >= 6  else 0
        ret_20d = float((close.iloc[-1] - close.iloc[-21]) / close.iloc[-21] * 100) if len(close) >= 21 else 0

        # Volume spike
        vol_avg   = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else float(volume.mean())
        vol_spike = float(volume.iloc[-1] / vol_avg) if vol_avg > 0 else 1.0

        score = 50.0
        score += min(ret_5d  * 3, 20)   # +20 max for 5-day gains
        score += min(ret_20d * 1.5, 15) # +15 max for 20-day gains
        score += min((vol_spike - 1) * 7, 15)  # +15 for volume surge
        # Penalise negative momentum
        if ret_5d < 0:
            score += max(ret_5d * 3, -20)
        return float(max(0, min(100, score)))
    except Exception:
        return 50.0


# ─────────────────────────────────────────────
# Main predictor
# ─────────────────────────────────────────────

def predict(ticker: str,
            df: pd.DataFrame,
            news_result: dict = None,
            short: int = config.SMA_SHORT,
            long:  int = config.SMA_LONG) -> dict:
    """
    Generate an AI prediction for a single stock.

    Args:
        ticker:      Stock symbol
        df:          OHLCV DataFrame
        news_result: Output of news_analyzer.analyze() — fetched if not provided
        short/long:  SMA periods

    Returns:
        Dict with:
          - ai_score:         0–100 confidence score
          - recommendation:   "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL"
          - sma_score:        0–100 (SMA component)
          - sentiment_score:  0–100 (News component)
          - momentum_score:   0–100 (Momentum component)
          - sentiment_label:  Human-readable sentiment
          - headlines:        List of scored news articles
    """
    # Fetch news if not provided
    if news_result is None:
        news_result = news_analyzer.analyze(ticker)

    # Component scores
    s_sma       = _sma_score(df, short, long)
    s_sentiment = _sentiment_score(news_result.get("sentiment_score", 0.0))
    s_momentum  = _momentum_score(df)

    # Weighted composite
    w_sma  = config.AI_WEIGHT_SMA       / 100
    w_sent = config.AI_WEIGHT_SENTIMENT / 100
    w_mom  = config.AI_WEIGHT_MOMENTUM  / 100

    ai_score = (s_sma * w_sma) + (s_sentiment * w_sent) + (s_momentum * w_mom)
    ai_score = round(float(ai_score), 1)

    # Recommendation
    if ai_score >= 80:
        recommendation = "STRONG BUY 🚀"
    elif ai_score >= config.AI_BUY_THRESHOLD:
        recommendation = "BUY 🟢"
    elif ai_score <= 20:
        recommendation = "STRONG SELL 💣"
    elif ai_score <= config.AI_SELL_THRESHOLD:
        recommendation = "SELL 🔴"
    else:
        recommendation = "HOLD 🟡"

    return {
        "ticker":           ticker,
        "ai_score":         ai_score,
        "recommendation":   recommendation,
        "sma_score":        round(s_sma, 1),
        "sentiment_score":  round(s_sentiment, 1),
        "momentum_score":   round(s_momentum, 1),
        "sentiment_label":  news_result.get("sentiment_label", "Neutral"),
        "headlines":        news_result.get("articles", []),
        "article_count":    news_result.get("article_count", 0),
    }


def predict_multiple(tickers: list, data_dict: dict, news_dict: dict = None) -> list:
    """
    Generate AI predictions for multiple tickers.

    Args:
        tickers:    List of ticker symbols
        data_dict:  Dict of {ticker: DataFrame}
        news_dict:  Dict of {ticker: news_result} — fetched if not provided

    Returns:
        List of prediction dicts, sorted by ai_score descending
    """
    if news_dict is None:
        news_dict = news_analyzer.analyze_multiple(tickers)

    results = []
    for ticker in tickers:
        if ticker not in data_dict:
            continue
        try:
            pred = predict(
                ticker,
                data_dict[ticker],
                news_result=news_dict.get(ticker),
            )
            results.append(pred)
        except Exception as e:
            print(f"  Prediction failed for {ticker}: {e}")

    return sorted(results, key=lambda x: x["ai_score"], reverse=True)
