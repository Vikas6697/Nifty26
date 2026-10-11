import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from pathlib import Path
import smtplib
from email.message import EmailMessage
import os

st.set_page_config(page_title="Nifty 50 AI Scanner", page_icon="📈", layout="wide")

TICKERS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS",
    "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS",
    "BEL.NS", "BHARTIARTL.NS", "CIPLA.NS", "COALINDIA.NS",
    "DRREDDY.NS", "EICHERMOT.NS", "ETERNAL.NS", "GRASIM.NS",
    "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS",
    "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "INDUSINDBK.NS",
    "INFY.NS", "ITC.NS", "JIOFIN.NS", "JSWSTEEL.NS",
    "KOTAKBANK.NS", "LT.NS", "M&M.NS", "MARUTI.NS",
    "NESTLEIND.NS", "NTPC.NS", "ONGC.NS", "POWERGRID.NS",
    "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SHRIRAMFIN.NS",
    "SUNPHARMA.NS", "TATACONSUM.NS", "TATASTEEL.NS", "TCS.NS",
    "TECHM.NS", "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS",
    "WIPRO.NS", "TMPV.NS",
]
BENCHMARK = "^NSEI"

def flatten_yf(df, ticker):
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        if ticker in df.columns.get_level_values(-1):
            df = df.xs(ticker, axis=1, level=-1)
        elif ticker in df.columns.get_level_values(0):
            df = df.xs(ticker, axis=1, level=0)
        else:
            df.columns = df.columns.get_level_values(0)
    return df

@st.cache_data(ttl=900, show_spinner=False)
def get_history(ticker, period="1y", interval="1d"):
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=True,
                     progress=False, threads=False)
    return flatten_yf(df, ticker)

def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def analyze(ticker, benchmark, horizon):
    df = get_history(ticker)
    if df.empty or len(df) < 60:
        return None
    need = {"Close", "High", "Low", "Volume"}
    if not need.issubset(df.columns):
        return None
    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    vol = df["Volume"].astype(float)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    sma200 = close.rolling(200).mean()
    rsi = calc_rsi(close)
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    macd_sig = macd.ewm(span=9, adjust=False).mean()
    volavg = vol.rolling(20).mean()
    atr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1).rolling(14).mean()
    high20 = high.shift(1).rolling(20).max()
    low20 = low.shift(1).rolling(20).min()
    price = float(close.iloc[-1])
    score = 0
    evidence = []
    if price > ema20.iloc[-1]: score += 15; evidence.append("Price > EMA20")
    if ema20.iloc[-1] > ema50.iloc[-1]: score += 15; evidence.append("EMA20 > EMA50")
    if pd.notna(sma200.iloc[-1]) and price > sma200.iloc[-1]: score += 15; evidence.append("Price > SMA200")
    if pd.notna(rsi.iloc[-1]) and 50 <= rsi.iloc[-1] <= 68: score += 10; evidence.append("RSI 50–68")
    if macd.iloc[-1] > macd_sig.iloc[-1]: score += 10; evidence.append("MACD > signal")
    vr = vol.iloc[-1] / volavg.iloc[-1] if pd.notna(volavg.iloc[-1]) and volavg.iloc[-1] else np.nan
    if pd.notna(vr) and vr >= 1.3: score += 10; evidence.append("Volume ≥ 1.3x average")
    if pd.notna(high20.iloc[-1]) and price > high20.iloc[-1]: score += 15; evidence.append("20-day high breakout")
    aligned = pd.concat([close.rename("stock"), benchmark.rename("nifty")], axis=1).dropna()
    rel = np.nan
    if len(aligned) >= 22:
        rel = ((aligned.stock.iloc[-1] / aligned.stock.iloc[-22] - 1) -
               (aligned.nifty.iloc[-1] / aligned.nifty.iloc[-22] - 1)) * 100
        if rel > 0: score += 10; evidence.append("Outperforming Nifty")
    if horizon == "Intraday":
        # Daily data only: explicitly avoid implying true intraday scanning.
        note = "Daily-data proxy only; use 5/15-minute live charts for intraday confirmation."
    elif horizon == "Swing (2–10 days)":
        note = "Daily trend and breakout screen; verify chart and liquidity before entry."
    else:
        note = "Daily trend proxy; review weekly chart and fundamentals before entry."
    if score >= 70: signal = "Bullish setup"
    elif score >= 50: signal = "Mixed / watch"
    else: signal = "Weak / bearish"
    a = float(atr.iloc[-1]) if pd.notna(atr.iloc[-1]) else np.nan
    return {
        "Ticker": ticker.replace(".NS", ""),
        "Date": str(df.index[-1].date()),
        "Price": round(price, 2),
        "Score": int(score),
        "Signal": signal,
        "RSI": round(float(rsi.iloc[-1]), 1) if pd.notna(rsi.iloc[-1]) else np.nan,
        "Volume x avg": round(float(vr), 2) if pd.notna(vr) else np.nan,
        "Relative strength vs Nifty (%)": round(float(rel), 2) if pd.notna(rel) else np.nan,
        "ATR14": round(a, 2) if np.isfinite(a) else np.nan,
        "Illustrative stop (price - 1.5 ATR)": round(price - 1.5*a, 2) if np.isfinite(a) else np.nan,
        "Illustrative target (price + 2 ATR)": round(price + 2*a, 2) if np.isfinite(a) else np.nan,
        "Evidence": "; ".join(evidence) if evidence else "No bullish rules triggered",
        "Note": note,
    }

def send_email_alert(df, email_to, sender, password, smtp_host, smtp_port, score_min):
    alerts = df[df["Score"] >= score_min]
    if alerts.empty:
        return False, "No stocks met the alert threshold."
    msg = EmailMessage()
    msg["Subject"] = f"Nifty 50 scanner alert — {len(alerts)} setup(s)"
    msg["From"] = sender
    msg["To"] = email_to
    msg.set_content("Rule-based Nifty 50 screening results (not buy/sell advice):\n\n" +
                    alerts[["Ticker", "Price", "Score", "Signal", "RSI", "Evidence"]].to_string(index=False))
    with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
    return True, f"Email sent with {len(alerts)} qualifying setup(s)."

st.title("📈 Nifty 50 Bullish Setup Scanner")
st.caption("Dashboard + optional email alerts | Historical Yahoo Finance data | Rule-based, not a prediction guarantee")

with st.sidebar:
    st.header("Scanner settings")
    horizon = st.selectbox("Trading horizon", ["Swing (2–10 days)", "Positional (2–12 weeks)", "Intraday"])
    min_score = st.slider("Minimum bullish score", 0, 100, 60, 5)
    refresh = st.button("🔄 Refresh data")
    st.markdown("---")
    st.write("Data source: Yahoo Finance. Data may be delayed/incomplete.")
    st.write("Intraday mode uses daily data as a proxy and is NOT a live intraday scanner.")

if refresh:
    get_history.clear()

if "scan_df" not in st.session_state or refresh:
    with st.spinner("Scanning Nifty 50 stocks. This may take a few minutes..."):
        bench_df = get_history(BENCHMARK)
        benchmark = bench_df["Close"].dropna() if not bench_df.empty and "Close" in bench_df else pd.Series(dtype=float)
        rows = []
        if benchmark.empty:
            st.error("Could not download Nifty benchmark data. Try again later.")
        else:
            progress = st.progress(0)
            for i, ticker in enumerate(TICKERS, 1):
                try:
                    result = analyze(ticker, benchmark, horizon)
                    if result:
                        rows.append(result)
                except Exception:
                    pass
                progress.progress(i / len(TICKERS))
            st.session_state.scan_df = pd.DataFrame(rows)
            progress.empty()

df = st.session_state.get("scan_df", pd.DataFrame())
if not df.empty:
    df = df.sort_values(["Score", "Relative strength vs Nifty (%)"], ascending=False)
    st.subheader("Market scan")
    c1, c2, c3 = st.columns(3)
    c1.metric("Stocks scanned", len(df))
    c2.metric("Bullish setups (score ≥ 70)", int((df["Score"] >= 70).sum()))
    c3.metric("Latest data date", str(df["Date"].max()))
    tab1, tab2, tab3 = st.tabs(["🏆 Top ranked", "📋 All stocks", "🔔 Email alerts"])
    with tab1:
        top = df[df["Score"] >= min_score].head(15)
        if top.empty:
            st.info("No stocks meet the selected score threshold. Lower the threshold or refresh later.")
        else:
            st.dataframe(top, use_container_width=True, hide_index=True)
    with tab2:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download scan CSV", df.to_csv(index=False).encode("utf-8"),
                           file_name="nifty50_scan_results.csv", mime="text/csv")
    with tab3:
        st.write("Optional SMTP email alert. For Gmail, use an App Password; do not use your normal account password.")
        st.warning("Email credentials are entered only for this running session. Do not share the app with credentials embedded in code.")
        email_to = st.text_input("Recipient email")
        sender = st.text_input("Sender email (SMTP login)")
        password = st.text_input("SMTP app password", type="password")
        smtp_host = st.text_input("SMTP host", value="smtp.gmail.com")
        smtp_port = st.number_input("SMTP port", value=587, step=1)
        alert_score = st.slider("Send alerts for score at least", 0, 100, 70, 5, key="alert_score")
        if st.button("Send qualifying email now"):
            if not all([email_to, sender, password, smtp_host]):
                st.error("Fill in all email fields first.")
            else:
                try:
                    ok, message = send_email_alert(df, email_to, sender, password, smtp_host, smtp_port, alert_score)
                    (st.success if ok else st.info)(message)
                except Exception as exc:
                    st.error(f"Email could not be sent: {exc}")
else:
    st.info("No scan results yet. Check your connection and refresh.")

st.markdown("---")
st.subheader("How to interpret the score")
st.write("70–100: stronger bullish evidence under these rules; 50–65: mixed/watch; below 50: weaker bullish evidence. Scores are heuristic ranks, not probabilities of profit.")
st.warning("This dashboard does not place trades. Verify live prices, current Nifty constituents, corporate news, liquidity and risk levels independently. Price gaps can exceed stop-losses. Paper-test before using real money.")
