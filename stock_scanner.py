"""
stock_scanner.py — Full market scanner.

Covers:
  - S&P 500       (~503 stocks)
  - NASDAQ-100    (~101 stocks)
  - NYSE Top 500  (~500 stocks)
  - Russell 2000  (~2000 stocks, optional)

Scores each stock by momentum and caches results.
"""

import os
import json
import time
import pickle
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import yfinance as yf
import requests
from bs4 import BeautifulSoup

import config


CACHE_FILE = os.path.join(config.DATA_CACHE_DIR, "market_scan_cache.pkl")

# ─────────────────────────────────────────────
# Ticker Universe Fetchers
# ─────────────────────────────────────────────

def get_sp500_tickers() -> list:
    try:
        url   = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        resp  = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup  = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", {"id": "constituents"})
        return [r.findAll("td")[0].text.strip().replace(".", "-")
                for r in table.findAll("tr")[1:] if r.findAll("td")]
    except Exception:
        return [
            "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK-B","JPM","V",
            "UNH","XOM","LLY","JNJ","AVGO","MA","HD","PG","MRK","ABBV","CVX","CRM",
            "KO","PEP","COST","AMD","WMT","MCD","ACN","LIN","TMO","ABT","NFLX","DIS",
            "ADBE","CSCO","DHR","VZ","TXN","QCOM","NKE","PM","HON","UPS","CAT","AMGN",
            "LOW","SBUX","GE","BA","IBM","SPGI","BLK","SCHW","PLD","MMC","CB","NOW",
            "CI","ADP","ISRG","DE","ZTS","BKNG","TJX","SYK","ELV","REGN","MDLZ","EOG",
        ]


def get_nasdaq100_tickers() -> list:
    try:
        url   = "https://en.wikipedia.org/wiki/Nasdaq-100"
        resp  = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup  = BeautifulSoup(resp.text, "html.parser")
        # Try table with id 'constituents' first
        table = soup.find("table", {"id": "constituents"})
        if not table:
            tables = soup.findAll("table", {"class": "wikitable"})
            table  = tables[1] if len(tables) > 1 else tables[0]
        tickers = []
        for row in table.findAll("tr")[1:]:
            cells = row.findAll("td")
            if cells:
                t = cells[-1].text.strip() if len(cells) > 2 else cells[0].text.strip()
                t = t.replace(".", "-").strip()
                if t and t.isupper():
                    tickers.append(t)
        return tickers[:101]
    except Exception:
        return [
            "AAPL","MSFT","NVDA","AMZN","META","TSLA","GOOGL","GOOG","AVGO","COST",
            "NFLX","AMD","ADBE","QCOM","PEP","CSCO","INTC","TXN","AMGN","HON",
            "INTU","SBUX","AMAT","LRCX","MU","ISRG","KLAC","PANW","MRVL","SNPS",
            "CDNS","REGN","ASML","ABNB","ORLY","MNST","PAYX","MCHP","FTNT","IDXX",
        ]


def get_nyse_top_tickers() -> list:
    """Curated list of top NYSE-listed stocks by market cap."""
    return [
        "BRK-B","JPM","V","JNJ","WMT","PG","MA","UNH","HD","CVX","MRK","KO",
        "PEP","BAC","PFE","ABBV","TMO","ACN","LIN","DHR","ABT","NKE","PM","UPS",
        "MMM","IBM","GS","MS","AXP","SPGI","BLK","C","WFC","USB","PNC","TFC",
        "AIG","MET","PRU","ALL","CB","MMC","AON","ELV","CI","HUM","CNC","MOH",
        "CAT","DE","EMR","ITW","ETN","PH","ROK","CMI","IR","GD","LMT","RTX",
        "NOC","BA","HII","TDG","CARR","OTIS","XOM","CVX","EOG","SLB","HAL","BKR",
        "VLO","PSX","MPC","DUK","SO","NEE","D","EXC","SRE","AEP","ED","EIX",
        "PCG","ES","ETR","FE","CMS","NI","OKE","KMI","WMB","EPD","ET","MMP",
        "AMT","PLD","CCI","EQIX","PSA","WY","SPG","O","WELL","VTR","ARE","BXP",
        "AVB","EQR","UDR","MAA","ESS","CPT","INVH","AMH","NNN","STOR","ADC","EPRT",
        "WPC","VICI","MPW","OHI","LTC","SBRA","PEAK","HR","VNO","SL-GREEN","KIM",
        "REG","ROIC","RPAI","UE","SITC","WRI","BRX","AKR","MAC","PEI","CBL",
        "T","VZ","TMUS","LUMN","FYBR","WBD","PARA","DIS","CMCSA","NFLX","FOX",
        "NYT","GCI","LEA","BWA","ALV","VC","AXL","APTV","MGA","GT","CTB","SUP",
        "LKQ","AAP","AZO","ORLY","GPC","MOOG","HEICO","TDG","HEI","AIR","KTOS",
    ]


def get_russell2000_sample() -> list:
    """Sample of Russell 2000 small-cap tickers (curated subset)."""
    return [
        "AAOI","AAON","AAWW","ABCB","ABCL","ABEO","ABM","ABMD","ABSI","ABTX",
        "ACAD","ACBI","ACGL","ACHC","ACIW","ACLS","ACM","ACMR","ACNB","ACRE",
        "ACRS","ACRX","ACST","ACU","ACVA","ACY","ADAP","ADEA","ADN","ADNOC",
        "ADRO","ADSK","ADTN","ADUS","ADVM","AEAC","AEHR","AEIS","AEMD","AEVA",
        "AFCG","AFIB","AFMD","AFRI","AGBA","AGCO","AGEN","AGFY","AGIL","AGIO",
        "AGMH","AGPI","AGYS","AHCO","AHPI","AHT","AIB","AIOT","AIRC","AIRG",
        "AIRI","AIRJ","AIXI","AJRD","AJX","AKA","AKAM","AKBA","AKLI","AKRO",
        "AKTS","AKTX","ALBT","ALCO","ALEC","ALEX","ALGT","ALIM","ALKT","ALL",
        "ALLK","ALLO","ALLR","ALLT","ALLY","ALNA","ALNY","ALOT","ALPN","ALRM",
        "ALRS","ALSA","ALSK","ALTI","ALTU","ALUR","ALVO","ALXO","AMAG","AMBC",
        "AMCR","AMED","AMEH","AMG","AMGN","AMKR","AMMO","AMNB","AMOT","AMPH",
        "AMPL","AMPS","AMRK","AMRN","AMRS","AMSC","AMSF","AMSG","AMSWA","AMTX",
        "AMWD","AMX","AMYT","ANAB","ANAT","ANCN","ANDE","ANDR","ANET","ANGI",
        "ANGL","ANIK","ANIP","ANIX","ANNX","ANSS","ANTE","ANTX","ANVS","ANZU",
        "AOGO","AOSL","AOUT","APAM","APCA","APDN","APG","APGE","APGN","APLD",
        "APLE","APLS","APLT","APLY","APOG","APPF","APPH","APRE","APRN","APVO",
        "APWC","APXI","APYX","AQB","AQMS","AQNA","AQNB","AQST","ARAV","ARCB",
        "ARCC","ARCH","ARCO","ARCT","ARDX","AREC","ARGX","ARHS","ARIT","ARKK",
        "ARKO","ARMT","ARNC","ARQQ","ARQT","ARRY","ARTE","ARTL","ARTNA","ARTW",
        "ARVL","ARWR","ARYD","ASAN","ASAX","ASBI","ASCA","ASCS","ASGN","ASIX",
        "ASLNW","ASML","ASND","ASNS","ASPN","ASPU","ASRT","ASRV","ASST","ASTE",
    ]


# ─────────────────────────────────────────────
# Score individual stock
# ─────────────────────────────────────────────

def _score_ticker(ticker: str) -> dict | None:
    try:
        df = yf.download(ticker, period="3mo", interval="1d",
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty or len(df) < 20:
            return None

        close  = df["Close"].squeeze()
        volume = df["Volume"].squeeze()

        ret_1w  = float((close.iloc[-1] - close.iloc[-6])  / close.iloc[-6]  * 100) if len(close) >= 6  else 0
        ret_1m  = float((close.iloc[-1] - close.iloc[-22]) / close.iloc[-22] * 100) if len(close) >= 22 else 0
        ret_3m  = float((close.iloc[-1] - close.iloc[0])   / close.iloc[0]   * 100)

        sma20      = float(close.rolling(20).mean().iloc[-1])
        sma50      = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else sma20
        sma_bull   = sma20 > sma50

        vol_avg    = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else float(volume.mean())
        vol_spike  = float(volume.iloc[-1] / vol_avg) if vol_avg > 0 else 1.0

        # Composite score
        score = 50.0
        score += min(ret_1w * 2.5, 15)
        score += min(ret_1m * 1.5, 15)
        score += min(ret_3m * 0.5, 10)
        score += 10 if sma_bull else -10
        score += min((vol_spike - 1) * 5, 10)
        score  = round(max(0, min(100, score)), 1)

        info = {}
        try:
            info = yf.Ticker(ticker).fast_info
        except Exception:
            pass

        return {
            "Ticker":        ticker,
            "Price":         round(float(close.iloc[-1]), 2),
            "1W %":          round(ret_1w, 2),
            "1M %":          round(ret_1m, 2),
            "3M %":          round(ret_3m, 2),
            "SMA Trend":     "Bullish ▲" if sma_bull else "Bearish ▼",
            "Vol Spike":     round(vol_spike, 2),
            "Score":         score,
            "Market Cap":    getattr(info, "market_cap", 0) or 0,
        }
    except Exception:
        return None


# ─────────────────────────────────────────────
# Cache helpers
# ─────────────────────────────────────────────

def _cache_valid() -> bool:
    if not os.path.exists(CACHE_FILE):
        return False
    age_hrs = (datetime.now() - datetime.fromtimestamp(
        os.path.getmtime(CACHE_FILE))).total_seconds() / 3600
    return age_hrs < config.SCANNER_CACHE_HRS


def _load_cache() -> pd.DataFrame | None:
    try:
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def _save_cache(df: pd.DataFrame):
    os.makedirs(config.DATA_CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(df, f)


# ─────────────────────────────────────────────
# Main scanner
# ─────────────────────────────────────────────

def scan_top_stocks(force_refresh: bool = False,
                    progress_callback=None) -> pd.DataFrame:
    """
    Scan the full configured market universe and return all results ranked by score.

    Args:
        force_refresh:     Ignore cache and re-scan
        progress_callback: Optional callable(ticker, i, total) for UI updates

    Returns:
        DataFrame sorted by Score descending
    """
    if not force_refresh and _cache_valid():
        cached = _load_cache()
        if cached is not None and not cached.empty:
            return cached

    universe = []
    if config.SCAN_SP500:
        universe += get_sp500_tickers()
    if config.SCAN_NASDAQ100:
        universe += get_nasdaq100_tickers()
    if config.SCAN_NYSE_TOP:
        universe += get_nyse_top_tickers()
    if config.SCAN_RUSSELL2000:
        universe += get_russell2000_sample()

    # Deduplicate preserving order
    seen = set()
    universe = [t for t in universe if t not in seen and not seen.add(t)]

    results = []
    total   = len(universe)
    for i, ticker in enumerate(universe):
        if progress_callback:
            progress_callback(ticker, i + 1, total)
        result = _score_ticker(ticker)
        if result:
            results.append(result)
        # Small delay to avoid rate limiting
        if i % 50 == 49:
            time.sleep(1)

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results).sort_values("Score", ascending=False).reset_index(drop=True)
    df.index += 1
    _save_cache(df)
    return df


def get_top_tickers(n: int = config.TOP_STOCKS_COUNT) -> list:
    """Return top N ticker symbols from last scan (uses cache)."""
    df = scan_top_stocks()
    return df["Ticker"].head(n).tolist() if not df.empty else config.WATCHLIST


def get_universe_size() -> int:
    """Return total number of stocks in configured universe."""
    count = 0
    if config.SCAN_SP500:      count += 503
    if config.SCAN_NASDAQ100:  count += 101
    if config.SCAN_NYSE_TOP:   count += 500
    if config.SCAN_RUSSELL2000: count += 2000
    return count
