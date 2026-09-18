"""
dashboard.py — AI-Powered Stock Monitor & Auto-Trader Dashboard

Tabs:
  📊 Live Signals    — SMA crossover signals for your watchlist
  🔍 Top Stocks      — Auto-scanned best momentum stocks
  📰 AI Predictions  — News sentiment + AI scoring per stock
  🤖 Auto-Trader     — Paper/live trading control panel (internal simulator)
  🎯 Manual Signals  — Scan the full ~100-stock watchlist and decide what
                        to place yourself in the Webull app
  🗞️ All News        — Every headline for your watchlist in one feed,
                        newest first, with sentiment color-coding
  🔥 Dynamic Picks   — How the auto-trade watchlist is chosen from the
                        S&P 500 (momentum + news sentiment), and why

Run:
  streamlit run dashboard.py
"""

import time
from datetime import datetime

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

import config
import data_fetcher
import strategy
import news_analyzer
import ai_predictor
import stock_scanner
import dynamic_watchlist
import trader
from risk_manager import RiskManager

# ─────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Stock Monitor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stApp { background-color: #0f1117; color: #fff; }
section[data-testid="stSidebar"] { background-color: #1a1d2e; }

.badge-buy        { background:#00e676; color:#000; padding:3px 14px; border-radius:20px; font-weight:bold; font-size:13px; }
.badge-sell       { background:#ff5252; color:#fff; padding:3px 14px; border-radius:20px; font-weight:bold; font-size:13px; }
.badge-hold       { background:#ffc107; color:#000; padding:3px 14px; border-radius:20px; font-weight:bold; font-size:13px; }
.badge-sbuy       { background:#00c853; color:#000; padding:3px 14px; border-radius:20px; font-weight:bold; font-size:13px; }
.badge-ssell      { background:#b71c1c; color:#fff; padding:3px 14px; border-radius:20px; font-weight:bold; font-size:13px; }

.stock-card       { background:#1a1d2e; border:1px solid #2d2f45; border-radius:12px; padding:16px; margin-bottom:10px; }
.stock-card.buy   { border-left:4px solid #00e676; }
.stock-card.sell  { border-left:4px solid #ff5252; }
.stock-card.hold  { border-left:4px solid #ffc107; }

.ai-score-bar     { height:8px; border-radius:4px; margin-top:4px; }
.ticker-hdr       { font-size:20px; font-weight:bold; }
.price-big        { font-size:26px; font-weight:bold; color:#4fc3f7; }
.muted            { color:#b8bcd0; font-size:12px; }
.bull             { color:#00e676; }
.bear             { color:#ff5252; }

.news-card        { background:#12152a; border:1px solid #2d2f45; border-radius:8px; padding:10px 14px; margin:6px 0; }
.pos-score        { color:#00e676; font-weight:bold; }
.neg-score        { color:#ff5252; font-weight:bold; }
.neu-score        { color:#ffc107; font-weight:bold; }

.trade-log-entry  { background:#12152a; border-radius:6px; padding:8px 12px; margin:4px 0; font-size:13px; }

[data-testid="metric-container"] { background:#1a1d2e; border:1px solid #2d2f45; border-radius:8px; padding:10px; }
hr { border-color:#2d2f45; }

/* Buttons — explicit colors so secondary buttons aren't white-text-on-white */
.stButton > button {
    background-color: #1a1d2e;
    color: #fff !important;
    border: 1px solid #4a4d63;
}
.stButton > button:hover {
    border-color: #4fc3f7;
    color: #4fc3f7 !important;
}
.stButton > button[kind="primary"] {
    background-color: #ff5252;
    color: #fff !important;
    border: none;
}
.stButton > button[kind="primary"]:hover {
    background-color: #ff6e6e;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🤖 AI Stock Monitor")
    st.markdown("---")

    st.markdown("### 📋 Watchlist")
    use_dynamic = getattr(config, "USE_DYNAMIC_WATCHLIST", False)
    if use_dynamic:
        # Non-blocking: reads the cache only, never triggers a fresh ~500-stock
        # scan here. Building it happens only via the explicit "Recompute Now"
        # button in the 🔥 Dynamic Picks tab, where progress can be shown.
        dyn_data = dynamic_watchlist.get_cached_watchlist_only()
        if dyn_data and dyn_data.get("tickers"):
            default_tickers = dyn_data["tickers"]
            built_at = dyn_data.get("built_at", "")[:16].replace("T", " ")
            st.caption(
                "🔥 Dynamic mode: auto-picked from the S&P 500 by momentum + "
                f"news sentiment. Built: {built_at}. See the 🔥 Dynamic Picks "
                "tab for why. Edit below to override for this session."
            )
        else:
            default_tickers = getattr(config, "AUTO_TRADE_WATCHLIST", config.WATCHLIST[:15])
            st.caption(
                "🔥 Dynamic mode is on but hasn't been built yet — using the "
                "fixed fallback list for now. Open the 🔥 Dynamic Picks tab "
                "and click 'Recompute Now' (takes a few minutes, one-time)."
            )
    else:
        default_tickers = getattr(config, "AUTO_TRADE_WATCHLIST", config.WATCHLIST[:15])
        st.caption("Static list. For the full ~100-stock scan, use the 🎯 Manual Signals tab.")

    watchlist_input = st.text_area(
        "One ticker per line:",
        value="\n".join(default_tickers),
        height=180,
    )
    tickers = [t.strip().upper() for t in watchlist_input.strip().splitlines() if t.strip()]

    st.markdown("---")
    st.markdown("### ⚙️ Strategy")
    sma_short = st.slider("Short SMA", 5, 50,  config.SMA_SHORT)
    sma_long  = st.slider("Long SMA",  20, 200, config.SMA_LONG,  step=5)

    st.markdown("---")
    st.markdown("### 🔄 Refresh")
    st.caption("Off by default — this holds the app open in a sleep loop, which wastes resources on a free cloud deploy. Click the Refresh button above instead, or turn this on only when running locally.")
    auto_refresh = st.toggle("Auto-refresh", value=False)
    refresh_mins = st.selectbox("Interval (min)", [1, 5, 10, 15, 30], index=1)

    st.markdown("---")
    mode_color = "🟡" if config.PAPER_TRADING else "🔴"
    mode_label = f"PAPER TRADING ({config.BROKER.upper()})" if config.PAPER_TRADING else f"⚠️ LIVE TRADING ({config.BROKER.upper()})"
    st.markdown(f"**{mode_color} Mode: {mode_label}**")

    st.markdown("---")
    st.caption("⚠️ Educational use only. Not financial advice.")


# ─────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns([4, 3, 1])
with c1:
    st.markdown("# 🤖 AI Stock Monitor")
with c2:
    st.markdown(f"<div style='margin-top:14px;color:#aaa;'>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)
with c3:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ─────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Live Signals",
    "🔍 Top Stocks",
    "📰 AI Predictions",
    "🤖 Auto-Trader",
    "🎯 Manual Signals",
    "🗞️ All News",
    "🔥 Dynamic Picks",
])


# ══════════════════════════════════════════════
# TAB 1 — Live Signals
# ══════════════════════════════════════════════
with tab1:
    @st.cache_data(ttl=300)
    def load_df(ticker):
        return data_fetcher.fetch(ticker, use_cache=False)

    @st.cache_data(ttl=300)
    def get_sig(ticker, s, l):
        df = load_df(ticker)
        return strategy.get_latest_signal(df, ticker=ticker, short=s, long=l)

    signals = []
    with st.spinner("Fetching signals..."):
        for t in tickers:
            try:
                signals.append(get_sig(t, sma_short, sma_long))
            except Exception as e:
                signals.append({"ticker": t, "signal": "ERROR", "close": 0,
                                 "sma_short": 0, "sma_long": 0,
                                 "signal_strength": 0, "position_status": str(e), "date": "—"})

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🟢 BUY",  sum(1 for s in signals if s["signal"] == "BUY"))
    m2.metric("🔴 SELL", sum(1 for s in signals if s["signal"] == "SELL"))
    m3.metric("🟡 HOLD", sum(1 for s in signals if s["signal"] == "HOLD"))
    m4.metric("📋 Total", len(signals))

    st.markdown("<br>", unsafe_allow_html=True)

    # Signal cards — 3 columns
    cols = st.columns(3)
    for i, r in enumerate(signals):
        sig, tk, price = r["signal"], r["ticker"], r["close"]
        ss, sl = r["sma_short"], r["sma_long"]
        strength, pos, date = r["signal_strength"], r["position_status"], r["date"]

        badge_map  = {"BUY": '<span class="badge-buy">▲ BUY</span>',
                      "SELL": '<span class="badge-sell">▼ SELL</span>',
                      "HOLD": '<span class="badge-hold">— HOLD</span>'}
        card_map   = {"BUY": "buy", "SELL": "sell", "HOLD": "hold"}
        badge      = badge_map.get(sig, sig)
        card_cls   = card_map.get(sig, "hold")
        trend_cls  = "bull" if "Bullish" in pos else "bear"
        trend_icon = "▲" if "Bullish" in pos else "▼"

        with cols[i % 3]:
            st.markdown(f"""
            <div class="stock-card {card_cls}">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span class="ticker-hdr">{tk}</span>{badge}
                </div>
                <div class="price-big">${price:,.2f}</div>
                <div class="muted">SMA-{sma_short}: <b>${ss:,.2f}</b> &nbsp;|&nbsp; SMA-{sma_long}: <b>${sl:,.2f}</b></div>
                <div class="muted">MA Gap: <b>{strength:.2f}%</b></div>
                <div class="{trend_cls}" style="margin-top:5px;">{trend_icon} {pos}</div>
                <div class="muted">{date}</div>
            </div>""", unsafe_allow_html=True)

    # Chart section
    st.markdown("---")
    st.markdown("### 📉 Chart")
    sel = st.selectbox("Select ticker:", tickers, key="chart_sel")

    @st.cache_data(ttl=300)
    def build_chart(ticker, s, l):
        df = load_df(ticker)
        df = strategy.detect_signals(df, s, l)
        sc, lc = f"SMA_{s}", f"SMA_{l}"
        df = df.dropna(subset=[sc, lc])
        buys_df  = df[df["Signal"] == "BUY"]
        sells_df = df[df["Signal"] == "SELL"]

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.75, 0.25], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Price",
            increasing_line_color="#00e676", decreasing_line_color="#ff5252",
            increasing_fillcolor="#00e676", decreasing_fillcolor="#ff5252"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[sc], name=f"SMA-{s}",
            line=dict(color="#ffb300", width=1.5, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[lc], name=f"SMA-{l}",
            line=dict(color="#ef5350", width=1.5, dash="dash")), row=1, col=1)
        if not buys_df.empty:
            fig.add_trace(go.Scatter(x=buys_df.index, y=buys_df["Close"], mode="markers",
                name="BUY", marker=dict(symbol="triangle-up", size=14, color="#00e676",
                line=dict(color="white", width=1))), row=1, col=1)
        if not sells_df.empty:
            fig.add_trace(go.Scatter(x=sells_df.index, y=sells_df["Close"], mode="markers",
                name="SELL", marker=dict(symbol="triangle-down", size=14, color="#ff5252",
                line=dict(color="white", width=1))), row=1, col=1)
        colors = ["#00e676" if c >= o else "#ff5252" for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume",
            marker_color=colors, opacity=0.6), row=2, col=1)
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0f1117",
            plot_bgcolor="#1a1d2e", height=580,
            title=f"<b>{ticker}</b> — SMA-{s}/{l} Crossover",
            xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=50, b=0))
        fig.update_xaxes(gridcolor="#2d2f45")
        fig.update_yaxes(gridcolor="#2d2f45")
        return fig

    try:
        st.plotly_chart(build_chart(sel, sma_short, sma_long), use_container_width=True)
    except Exception as e:
        st.error(f"Chart error: {e}")


# ══════════════════════════════════════════════
# TAB 2 — Top Stocks
# ══════════════════════════════════════════════
with tab2:
    st.markdown("### 🔍 Top Momentum Stocks (Auto-Scanned)")
    st.caption(f"Scanning S&P 500 + NASDAQ-100 · Top {config.TOP_STOCKS_COUNT} by momentum score")

    if st.button("🔍 Run Full Scan Now", use_container_width=False):
        st.cache_data.clear()

    @st.cache_data(ttl=3600, show_spinner="Scanning top stocks (this takes ~60s)...")
    def scan_top():
        return stock_scanner.scan_top_stocks()

    try:
        top_df = scan_top()
        if top_df.empty:
            st.warning("Could not retrieve top stocks. Check your internet connection.")
        else:
            # Color-code by momentum score
            def color_score(val):
                if val >= 70: return "background-color:#003d1f; color:#00e676"
                if val >= 55: return "background-color:#1a2d00; color:#8bc34a"
                if val <= 30: return "background-color:#3d0000; color:#ff5252"
                return ""

            def color_return(val):
                if val > 5:  return "color:#00e676; font-weight:bold"
                if val > 0:  return "color:#8bc34a"
                if val < -5: return "color:#ff5252; font-weight:bold"
                if val < 0:  return "color:#ef9a9a"
                return ""

            styled = (top_df.style
                .map(color_score,   subset=["Score"])
                .map(color_return,  subset=["1W %", "1M %", "3M %"])
            )

            st.dataframe(styled, use_container_width=True, height=600)

            # Add top stocks to watchlist button
            if st.button("➕ Add Top 10 to Watchlist"):
                top10 = top_df["Ticker"].head(10).tolist()
                st.session_state["extra_tickers"] = top10
                st.success(f"Added to session watchlist: {', '.join(top10)}")
    except Exception as e:
        st.error(f"Scanner error: {e}")


# ══════════════════════════════════════════════
# TAB 3 — AI Predictions
# ══════════════════════════════════════════════
with tab3:
    st.markdown("### 📰 AI Predictions — News Sentiment + Technical Analysis")
    st.caption("AI Score = SMA Signal (40%) + News Sentiment (35%) + Price Momentum (25%)")

    pred_tickers = tickers
    if st.button("🤖 Run AI Predictions", use_container_width=False, key="run_pred"):
        st.cache_data.clear()

    @st.cache_data(ttl=600, show_spinner="Analyzing news & computing AI scores...")
    def run_predictions(tickers_tuple):
        tickers_list = list(tickers_tuple)
        data_dict = data_fetcher.fetch_multiple(tickers_list)
        news_dict = news_analyzer.analyze_multiple(tickers_list)
        preds     = ai_predictor.predict_multiple(tickers_list, data_dict, news_dict)
        return preds, news_dict

    try:
        preds, news_dict = run_predictions(tuple(pred_tickers))

        # Summary bar
        buys  = [p for p in preds if "BUY"  in p["recommendation"]]
        sells = [p for p in preds if "SELL" in p["recommendation"]]
        holds = [p for p in preds if "HOLD" in p["recommendation"]]

        a1, a2, a3, a4 = st.columns(4)
        a1.metric("🚀 Strong/BUY",  len(buys))
        a2.metric("🔴 Strong/SELL", len(sells))
        a3.metric("🟡 HOLD",        len(holds))
        a4.metric("📰 Avg Score",   f"{sum(p['ai_score'] for p in preds)/len(preds):.0f}/100" if preds else "—")

        st.markdown("<br>", unsafe_allow_html=True)

        # Prediction cards
        pcols = st.columns(2)
        for i, pred in enumerate(preds):
            tk   = pred["ticker"]
            sc   = pred["ai_score"]
            rec  = pred["recommendation"]
            sent = pred["sentiment_label"]
            smas = pred["sma_score"]
            sments = pred["sentiment_score"]
            smom = pred["momentum_score"]

            # Badge
            if "STRONG BUY" in rec:   badge = '<span class="badge-sbuy">🚀 STRONG BUY</span>'
            elif "BUY" in rec:         badge = '<span class="badge-buy">▲ BUY</span>'
            elif "STRONG SELL" in rec: badge = '<span class="badge-ssell">💣 STRONG SELL</span>'
            elif "SELL" in rec:        badge = '<span class="badge-sell">▼ SELL</span>'
            else:                      badge = '<span class="badge-hold">— HOLD</span>'

            # Score bar color
            bar_color = "#00e676" if sc >= 65 else "#ff5252" if sc <= 35 else "#ffc107"
            bar_width  = int(sc)

            with pcols[i % 2]:
                st.markdown(f"""
                <div class="stock-card hold" style="border-left:4px solid {bar_color};">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span class="ticker-hdr">{tk}</span>{badge}
                    </div>
                    <div style="margin:8px 0 4px;">
                        <b style="font-size:18px;color:{bar_color};">{sc:.0f}/100</b>
                        <span class="muted"> AI Score</span>
                    </div>
                    <div style="background:#2d2f45;border-radius:4px;height:8px;margin-bottom:10px;">
                        <div style="width:{bar_width}%;background:{bar_color};height:8px;border-radius:4px;"></div>
                    </div>
                    <div class="muted">📐 SMA Signal: <b>{smas:.0f}/100</b> &nbsp;|&nbsp;
                         📰 News: <b>{sments:.0f}/100</b> &nbsp;|&nbsp;
                         📈 Momentum: <b>{smom:.0f}/100</b></div>
                    <div style="margin-top:6px;">{sent}</div>
                </div>""", unsafe_allow_html=True)

                # News headlines for this ticker
                with st.expander(f"📰 {pred['article_count']} headlines for {tk}"):
                    articles = pred.get("headlines", [])
                    if not articles:
                        st.caption("No news found.")
                    for art in articles:
                        score = art["score"]
                        score_cls = "pos-score" if score > 0.1 else "neg-score" if score < -0.1 else "neu-score"
                        score_icon = "🟢" if score > 0.1 else "🔴" if score < -0.1 else "🟡"
                        st.markdown(f"""
                        <div class="news-card">
                            {score_icon} <span class="{score_cls}">{score:+.2f}</span> &nbsp;
                            <a href="{art['url']}" target="_blank" style="color:#4fc3f7;text-decoration:none;">
                                {art['title']}
                            </a>
                            <div class="muted">{art['source']} · {art['published']}</div>
                        </div>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"AI prediction error: {e}")
        st.exception(e)


# ══════════════════════════════════════════════
# TAB 4 — Auto-Trader
# ══════════════════════════════════════════════
with tab4:
    st.markdown("### 🤖 Auto-Trader Control Panel")

    # Mode banner
    if config.PAPER_TRADING:
        st.info(f"🟡 **PAPER TRADING MODE ({config.BROKER.upper()})** — All trades are simulated. No real money is involved.", icon="🟡")
    else:
        st.error(f"🔴 **LIVE TRADING ACTIVE ({config.BROKER.upper()})** — Real orders will be placed with real money!", icon="🔴")

    # Risk settings display
    with st.expander("⚙️ Risk Management Settings"):
        r1, r2, r3, r4, r5 = st.columns(5)
        r1.metric("Max Position",  f"{config.MAX_POSITION_PCT}%")
        r2.metric("Max Positions", config.MAX_OPEN_POSITIONS)
        r3.metric("Daily Loss Limit", f"-{config.DAILY_LOSS_LIMIT}%")
        r4.metric("Stop-Loss",     f"-{config.STOP_LOSS_PCT}%")
        r5.metric("Min AI Score",  f"{config.AI_MIN_SCORE}/100")
        st.caption("Edit these in `config.py`")

    st.markdown("---")

    # Portfolio summary
    @st.cache_data(ttl=60)
    def get_portfolio(tickers_tuple):
        prices = {}
        for t in tickers_tuple:
            try:
                df = data_fetcher.fetch(t, use_cache=True)
                prices[t] = float(df["Close"].iloc[-1])
            except Exception:
                pass
        return trader.get_portfolio_summary(prices), prices

    portfolio, prices = get_portfolio(tuple(tickers))

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("💵 Cash",          f"${portfolio['cash']:,.2f}")
    p2.metric("💼 Total Value",   f"${portfolio['total_value']:,.2f}")
    pnl_color = "normal" if portfolio['total_pnl'] >= 0 else "inverse"
    p3.metric("📈 Total P&L",    f"${portfolio['total_pnl']:+,.2f}", f"{portfolio['total_pnl_pct']:+.2f}%")
    p4.metric("📦 Open Positions", len(portfolio["positions"]))

    st.markdown("---")

    # Open positions table
    st.markdown("#### 📦 Open Positions")
    if portfolio["positions"]:
        pos_df = pd.DataFrame(portfolio["positions"])

        def style_pnl(val):
            if isinstance(val, (int, float)):
                return "color:#00e676;font-weight:bold" if val > 0 else "color:#ff5252;font-weight:bold" if val < 0 else ""
            return ""

        styled_pos = pos_df.style.map(style_pnl, subset=["P&L $", "P&L %"])
        st.dataframe(styled_pos, use_container_width=True)
    else:
        st.info("No open positions.")

    st.markdown("---")

    # Run auto-trader
    st.markdown("#### ▶️ Run AI Auto-Trader")
    col_run, col_stop, col_reset = st.columns(3)

    with col_run:
        if st.button("🚀 Run Auto-Trade Now", use_container_width=True, type="primary"):
            with st.spinner("Fetching predictions and executing trades..."):
                try:
                    # Get predictions
                    data_dict = data_fetcher.fetch_multiple(tickers)
                    news_dict = news_analyzer.analyze_multiple(tickers)
                    preds     = ai_predictor.predict_multiple(tickers, data_dict, news_dict)
                    risk      = RiskManager(config.PAPER_INITIAL_CAPITAL)
                    results   = trader.auto_trade(preds, prices, risk)

                    if results:
                        for res in results:
                            if res.get("success"):
                                action = res.get("action", "")
                                if action == "BUY":
                                    st.success(f"✅ {action} {res['ticker']} — {res['shares']} shares @ ${res['price']:.2f} | Score: {res['ai_score']:.0f}/100")
                                else:
                                    pnl = res.get('pnl', 0)
                                    st.success(f"✅ {action} {res['ticker']} — P&L: ${pnl:+.2f}")
                            else:
                                st.warning(f"⚠️ {res['ticker']}: {res.get('reason', 'Unknown')}")
                    else:
                        st.info("No trades executed — no signals met all criteria.")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Trade error: {e}")

    with col_stop:
        if st.button("🛑 Emergency STOP", use_container_width=True):
            risk = RiskManager()
            risk.emergency_halt("Manual emergency stop from dashboard")
            st.error("🛑 Trading halted! Resume in config or restart app.")

    with col_reset:
        if st.button("🔄 Reset Paper Portfolio", use_container_width=True):
            trader.reset_paper_portfolio()
            st.success(f"Portfolio reset to ${config.PAPER_INITIAL_CAPITAL:,.2f}")
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    # Trade log
    st.markdown("#### 📋 Trade History")
    log = portfolio.get("trade_log", [])
    if log:
        log_df = pd.DataFrame(reversed(log))

        def style_action(val):
            if val == "BUY":  return "background-color:#003d1f;color:#00e676;font-weight:bold"
            if val == "SELL": return "background-color:#3d0000;color:#ff5252;font-weight:bold"
            return ""

        styled_log = log_df.style.map(style_action, subset=["action"])
        st.dataframe(styled_log, use_container_width=True, height=300)
    else:
        st.info("No trades yet. Click 'Run Auto-Trade Now' to start.")

    # Disclaimer
    st.markdown("---")
    st.warning(
        "⚠️ **DISCLAIMER**: This is an algorithmic tool for educational purposes. "
        "No AI can guarantee stock market profits. Past performance does not predict future results. "
        "Always review trades before enabling LIVE mode. You are solely responsible for any investment decisions.",
        icon="⚠️"
    )


# ══════════════════════════════════════════════
# TAB 5 — Manual Signals (scan ~100 stocks, decide, place in Webull yourself)
# ══════════════════════════════════════════════
with tab5:
    st.markdown("### 🎯 Manual Signals — full watchlist scan")
    st.caption(
        f"Scans all {len(config.WATCHLIST)} stocks in config.WATCHLIST. Nothing here places any "
        f"order automatically — review it, then place matching trades yourself in the Webull app."
    )

    m_col1, m_col2, m_col3 = st.columns([2, 2, 2])
    with m_col1:
        include_news = st.checkbox(
            "Include news sentiment",
            value=False,
            help="Uses ~1 News-API request per stock. With ~100 stocks this can exhaust a free-tier "
                 "daily quota in one scan. Leave off for a fast SMA + momentum-only scan.",
        )
    with m_col2:
        show_filter = st.selectbox("Show", ["Non-HOLD only", "BUY only", "SELL only", "All"], index=0)
    with m_col3:
        assumed_portfolio = st.number_input(
            "Assumed portfolio $ (for suggested share size)", min_value=1000, value=10000, step=1000
        )

    run_scan = st.button("🔍 Scan Full Watchlist", type="primary", use_container_width=False)

    @st.cache_data(ttl=1800, show_spinner="Scanning full watchlist...")
    def run_manual_scan(tickers_tuple, use_news: bool):
        tickers_list = list(tickers_tuple)
        data_dict = data_fetcher.fetch_multiple(tickers_list)
        if use_news:
            news_dict = news_analyzer.analyze_multiple(tickers_list)
        else:
            # Skip News API entirely — neutral sentiment for every ticker.
            neutral = {
                "sentiment_score": 0.0, "sentiment_label": "Neutral ➡️",
                "articles": [], "article_count": 0,
            }
            news_dict = {t: dict(neutral) for t in tickers_list}
        preds = ai_predictor.predict_multiple(tickers_list, data_dict, news_dict)
        return preds

    if run_scan:
        st.cache_data.clear()

    if "manual_scan_ran" not in st.session_state:
        st.session_state["manual_scan_ran"] = False
    if run_scan:
        st.session_state["manual_scan_ran"] = True

    if st.session_state["manual_scan_ran"]:
        try:
            preds = run_manual_scan(tuple(config.WATCHLIST), include_news)

            risk_helper = RiskManager(assumed_portfolio)
            rows = []
            for p in preds:
                if show_filter == "BUY only" and "BUY" not in p["recommendation"]:
                    continue
                if show_filter == "SELL only" and "SELL" not in p["recommendation"]:
                    continue
                if show_filter == "Non-HOLD only" and "HOLD" in p["recommendation"]:
                    continue

                price = 0.0
                try:
                    price = float(data_fetcher.fetch(p["ticker"], use_cache=True)["Close"].iloc[-1])
                except Exception:
                    pass
                suggested_shares = risk_helper.position_size(assumed_portfolio, price) if price > 0 else 0

                rows.append({
                    "Ticker": p["ticker"],
                    "Recommendation": p["recommendation"],
                    "AI Score": p["ai_score"],
                    "Price": round(price, 2),
                    "SMA Score": p["sma_score"],
                    "Sentiment": p["sentiment_label"] if include_news else "— (not scanned)",
                    "Momentum": p["momentum_score"],
                    "Suggested Shares": suggested_shares,
                    "Suggested $": round(suggested_shares * price, 2),
                })

            if not rows:
                st.info(f"No stocks currently match filter: {show_filter}")
            else:
                result_df = pd.DataFrame(rows).sort_values("AI Score", ascending=False).reset_index(drop=True)

                def style_rec(val):
                    if "STRONG BUY" in val:  return "background-color:#003d1f;color:#00e676;font-weight:bold"
                    if "BUY" in val:         return "background-color:#0a2818;color:#00e676"
                    if "STRONG SELL" in val: return "background-color:#3d0000;color:#ff5252;font-weight:bold"
                    if "SELL" in val:        return "background-color:#280a0a;color:#ff5252"
                    return "color:#ffc107"

                styled = result_df.style.map(style_rec, subset=["Recommendation"])
                st.dataframe(styled, use_container_width=True, height=600)

                buy_tickers = [r["Ticker"] for r in rows if "BUY" in r["Recommendation"]]
                sell_tickers = [r["Ticker"] for r in rows if "SELL" in r["Recommendation"]]
                bcol, scol = st.columns(2)
                with bcol:
                    if buy_tickers:
                        st.markdown("**BUY candidates — copy into Webull search:**")
                        st.code(", ".join(buy_tickers))
                with scol:
                    if sell_tickers:
                        st.markdown("**SELL candidates — copy into Webull search:**")
                        st.code(", ".join(sell_tickers))

                st.caption(
                    "Suggested shares/$ are sized at MAX_POSITION_PCT of your assumed portfolio value — "
                    "a reference for your manual order, not a real position (this app never places "
                    "orders in Webull)."
                )
        except Exception as e:
            st.error(f"Scan error: {e}")
    else:
        st.info("Click **Scan Full Watchlist** to run the ~100-stock scan.")


# ══════════════════════════════════════════════
# TAB 6 — All News
# ══════════════════════════════════════════════
with tab6:
    st.markdown("### 🗞️ All News — every headline for your watchlist, newest first")

    n_col1, n_col2, n_col3 = st.columns([2, 2, 2])
    with n_col1:
        news_scope = st.radio(
            "Scope",
            ["Sidebar watchlist (fast)", "Full ~100-stock watchlist"],
            index=0,
            help="Sidebar list uses ~15 News-API requests. The full list uses ~100 — "
                 "can exhaust a free-tier daily quota in one click.",
        )
    with n_col2:
        news_sentiment_filter = st.selectbox(
            "Filter", ["All", "Bullish only", "Bearish only", "Neutral only"], index=0
        )
    with n_col3:
        news_ticker_filter = st.multiselect("Only these tickers (optional)", options=sorted(
            config.WATCHLIST if news_scope.startswith("Full") else tickers
        ))

    run_news = st.button("🗞️ Fetch All News", type="primary", use_container_width=False)

    @st.cache_data(ttl=900, show_spinner="Fetching headlines...")
    def run_news_feed(tickers_tuple):
        tickers_list = list(tickers_tuple)
        news_dict = news_analyzer.analyze_multiple(tickers_list)
        feed = []
        for tk, info in news_dict.items():
            for art in info.get("articles", []):
                feed.append({
                    "ticker":    tk,
                    "title":     art["title"],
                    "source":    art["source"],
                    "url":       art["url"],
                    "published": art["published"],
                    "score":     art["score"],
                })
        # Newest first (falls back to ticker order for missing/blank dates)
        feed.sort(key=lambda a: a["published"], reverse=True)
        return feed

    if run_news:
        st.cache_data.clear()

    if "news_feed_ran" not in st.session_state:
        st.session_state["news_feed_ran"] = False
    if run_news:
        st.session_state["news_feed_ran"] = True

    if st.session_state["news_feed_ran"]:
        try:
            scope_tickers = config.WATCHLIST if news_scope.startswith("Full") else tickers
            feed = run_news_feed(tuple(scope_tickers))

            if news_ticker_filter:
                feed = [a for a in feed if a["ticker"] in news_ticker_filter]
            if news_sentiment_filter == "Bullish only":
                feed = [a for a in feed if a["score"] > 0.1]
            elif news_sentiment_filter == "Bearish only":
                feed = [a for a in feed if a["score"] < -0.1]
            elif news_sentiment_filter == "Neutral only":
                feed = [a for a in feed if -0.1 <= a["score"] <= 0.1]

            b1, b2, b3, b4 = st.columns(4)
            b1.metric("📰 Headlines", len(feed))
            b2.metric("🟢 Bullish", len([a for a in feed if a["score"] > 0.1]))
            b3.metric("🔴 Bearish", len([a for a in feed if a["score"] < -0.1]))
            b4.metric("🟡 Neutral", len([a for a in feed if -0.1 <= a["score"] <= 0.1]))

            st.markdown("<br>", unsafe_allow_html=True)

            if not feed:
                st.info("No headlines match the current filters.")
            else:
                for art in feed:
                    score = art["score"]
                    score_cls = "pos-score" if score > 0.1 else "neg-score" if score < -0.1 else "neu-score"
                    score_icon = "🟢" if score > 0.1 else "🔴" if score < -0.1 else "🟡"
                    st.markdown(f"""
                    <div class="news-card">
                        <span style="background:#2d2f45;color:#4fc3f7;border-radius:6px;padding:2px 8px;font-weight:bold;font-size:12px;">{art['ticker']}</span>
                        &nbsp;{score_icon} <span class="{score_cls}">{score:+.2f}</span> &nbsp;
                        <a href="{art['url']}" target="_blank" style="color:#4fc3f7;text-decoration:none;">
                            {art['title']}
                        </a>
                        <div class="muted">{art['source']} · {art['published']}</div>
                    </div>""", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"News feed error: {e}")
    else:
        st.info(
            "Click **Fetch All News** to pull every headline for your watchlist into one feed. "
            "Uses the News API quota — pick 'Sidebar watchlist' to keep it light."
        )


# ══════════════════════════════════════════════
# TAB 7 — Dynamic Picks
# ══════════════════════════════════════════════
with tab7:
    st.markdown("### 🔥 Dynamic Picks — auto-selected from the S&P 500")

    pool_n = getattr(config, "DYNAMIC_WATCHLIST_POOL", 25)
    size_n = getattr(config, "DYNAMIC_WATCHLIST_SIZE", 15)
    cache_hrs = getattr(config, "DYNAMIC_WATCHLIST_CACHE_HRS", 12)

    st.caption(
        f"Stage 1: every S&P 500 stock (~503) is scored on price/volume momentum only — free, no news calls. "
        f"Stage 2: news sentiment is checked on just the top {pool_n} of those. "
        f"The best {size_n} by a combined score (60% momentum + 40% sentiment) become the actual auto-trade watchlist."
    )

    if not getattr(config, "USE_DYNAMIC_WATCHLIST", False):
        st.warning(
            "USE_DYNAMIC_WATCHLIST is off in config.py — the scheduled auto-trader is currently using the "
            "fixed AUTO_TRADE_WATCHLIST instead. This tab still shows what the dynamic pick *would* be."
        )

    dp_col1, dp_col2 = st.columns([1, 3])
    with dp_col1:
        recompute = st.button("🔄 Recompute Now", type="primary")
    with dp_col2:
        st.caption(f"Cached for {cache_hrs}h between recomputes to limit news-API usage on scheduled runs. "
                   f"First build scans ~503 stocks and takes a few minutes.")

    try:
        cached = dynamic_watchlist.get_cached_watchlist_only()

        if recompute or cached is None:
            progress_bar = st.progress(0, text="Scanning S&P 500 momentum (stage 1 of 2)...")

            def _progress(i, total):
                pct = min(int(i / total * 100), 100)
                progress_bar.progress(pct, text=f"Scanning S&P 500 momentum (stage 1 of 2)... {i}/{total}")

            with st.spinner(f"Building the dynamic watchlist — checking news sentiment on the top {pool_n} (stage 2 of 2)..."):
                data = dynamic_watchlist.build_watchlist(force_refresh=True, progress_callback=_progress)
            progress_bar.empty()
        else:
            data = cached

        built_at = data.get("built_at", "")[:16].replace("T", " ")
        if built_at:
            st.caption(f"Last built: {built_at}")

        rows = []
        picked_tickers = set(data.get("tickers", []))
        for d in data.get("pool_detail", []):
            rows.append({
                "Picked":          "✅" if d["ticker"] in picked_tickers else "",
                "Ticker":          d["ticker"],
                "Combined Score":  d["combined_score"],
                "Momentum":        d["momentum_score"],
                "Sentiment":       d["sentiment_label"],
                "Sentiment Score": round(d["sentiment_score"], 2),
                "Articles":        d["article_count"],
            })

        if not rows:
            st.info("No results yet — click **Recompute Now** to run the scan.")
        else:
            picks_df = pd.DataFrame(rows)

            def color_combined(val):
                if val >= 70: return "background-color:#003d1f; color:#00e676"
                if val >= 55: return "background-color:#1a2d00; color:#8bc34a"
                if val <= 35: return "background-color:#3d0000; color:#ff5252"
                return ""

            styled = picks_df.style.map(color_combined, subset=["Combined Score"])
            st.dataframe(styled, use_container_width=True, height=560)

            st.caption(
                f"✅ = one of the {len(picked_tickers)} tickers currently selected. "
                "These feed the scheduled auto-trader and the sidebar's default watchlist "
                "when USE_DYNAMIC_WATCHLIST is on — edit the sidebar list to override for this session only."
            )
    except Exception as e:
        st.error(f"Dynamic watchlist error: {e}")
        st.exception(e)


# ─────────────────────────────────────────────────────────────
# Auto-refresh
# ─────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(refresh_mins * 60)
    st.cache_data.clear()
    st.rerun()
