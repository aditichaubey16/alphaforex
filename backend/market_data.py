"""Live FX data via yfinance, plus technical indicators computed in-process
with pandas. No fundamentals exist for a currency pair (no P/E, no ROE), so
every signal here is price-action-based: moving averages, RSI, MACD, ATR.

Every concern flag is a named threshold rule and every recommendation lists
the exact inputs that produced it — same transparency principle as
`../alphadesk-solo/backend/market_data.py`, applied to technicals instead of
fundamentals. No LLM step; nothing is inferred.
"""
from __future__ import annotations

import time
from functools import wraps

import pandas as pd
import yfinance as yf

# ---- live-data caching ----
#
# Every pair page load and every Live-Scan-style sweep triggers one live
# yfinance call per pair. AlphaDesk hit Yahoo's per-IP rate limit on Render
# once real traffic showed up (see its README) — a short in-process TTL
# cache here means concurrent viewers looking at the same pair within the
# window share one upstream call instead of one each, without staling out
# a single-user session (prices still update within the TTL).


def _ttl_cache(ttl_seconds: float):
    """Caches by (symbol, ...other args), keyed per-function. Returns a
    shallow copy of dict/list results so a caller mutating its copy (e.g.
    main.py adding `open_today` onto a snapshot dict) can't corrupt what's
    served to the next caller. Failed calls (exceptions) are never cached,
    so a transient yfinance error doesn't get "stuck" for the TTL window."""

    def decorator(fn):
        cache: dict[tuple, tuple[object, float]] = {}

        @wraps(fn)
        def wrapper(*args):
            now = time.time()
            cached = cache.get(args)
            if cached and now - cached[1] < ttl_seconds:
                result = cached[0]
            else:
                result = fn(*args)
                cache[args] = (result, now)
            if isinstance(result, dict):
                return dict(result)
            if isinstance(result, list):
                return list(result)
            return result

        return wrapper

    return decorator


# ---- indicator math (plain pandas, no external TA library) ----


def _rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """Simple-moving-average RSI (not Wilder's smoothing) — easier to explain
    and audit than the smoothed variant; close enough for a rule scan."""
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _round(x, digits=5):
    return None if x is None or pd.isna(x) else round(float(x), digits)


@_ttl_cache(ttl_seconds=30)
def fetch_snapshot(symbol: str) -> dict:
    """Live price plus every technical indicator the recommendation and flag
    rules use. `history(period="1y")` (daily bars) is fetched once and reused
    for all indicator math — SMA200 needs ~200 trading days, comfortably
    inside a year."""
    t = yf.Ticker(symbol)
    info = t.info or {}
    hist = t.history(period="1y")
    if hist.empty:
        raise ValueError(f"No price history returned for {symbol}")

    closes = hist["Close"]
    price = info.get("regularMarketPrice") or info.get("currentPrice") or float(closes.iloc[-1])
    prev_close = info.get("regularMarketPreviousClose") or (float(closes.iloc[-2]) if len(closes) > 1 else None)

    sma20 = closes.rolling(20).mean()
    sma50 = closes.rolling(50).mean()
    sma200 = closes.rolling(200).mean()
    rsi14 = _rsi(closes)
    macd_line, macd_signal, macd_hist = _macd(closes)
    atr14 = _atr(hist)

    week_ago = closes.iloc[-6] if len(closes) > 6 else None
    month_ago = closes.iloc[-22] if len(closes) > 22 else None

    hi_52w = float(hist["High"].max())
    lo_52w = float(hist["Low"].min())
    atr_val = _round(atr14.iloc[-1], 6)
    quote_currency = symbol.replace("=X", "")[3:6]

    snapshot = {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName") or symbol,
        "quote_currency": quote_currency,
        "price": _round(price),
        "prev_close": _round(prev_close),
        "change_pct": _round((price - prev_close) / prev_close * 100, 2) if prev_close else None,
        "week_change_pct": _round((price - week_ago) / week_ago * 100, 2) if week_ago else None,
        "month_change_pct": _round((price - month_ago) / month_ago * 100, 2) if month_ago else None,
        "day_high": _round(info.get("regularMarketDayHigh") or hist["High"].iloc[-1]),
        "day_low": _round(info.get("regularMarketDayLow") or hist["Low"].iloc[-1]),
        "52w_high": _round(hi_52w),
        "52w_low": _round(lo_52w),
        "sma20": _round(sma20.iloc[-1]),
        "sma50": _round(sma50.iloc[-1]),
        "sma200": _round(sma200.iloc[-1]) if len(closes) >= 200 else None,
        "rsi14": _round(rsi14.iloc[-1], 1),
        "macd_line": _round(macd_line.iloc[-1], 6),
        "macd_signal": _round(macd_signal.iloc[-1], 6),
        "macd_hist": _round(macd_hist.iloc[-1], 6),
        "macd_hist_prev": _round(macd_hist.iloc[-2], 6) if len(macd_hist) > 1 else None,
        "atr14": atr_val,
        "atr_pct": _round(atr_val / price * 100, 2) if atr_val and price else None,
    }
    return snapshot


_VALID_HISTORY_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y"}


@_ttl_cache(ttl_seconds=300)
def fetch_price_history(symbol: str, period: str = "6mo") -> list[dict]:
    if period not in _VALID_HISTORY_PERIODS:
        period = "6mo"
    t = yf.Ticker(symbol)
    hist = t.history(period=period)
    if hist.empty:
        return []
    return [{"date": date.strftime("%Y-%m-%d"), "close": round(float(row["Close"]), 5)} for date, row in hist.iterrows()]


@_ttl_cache(ttl_seconds=300)
def fetch_indicator_history(symbol: str, period: str = "6mo") -> list[dict]:
    """Full time series (not just the latest value) for the charts on the
    research page: close price with SMA20/50/200 overlay, RSI14, and MACD
    histogram. Indicators are computed on 1y of data internally (so SMA200
    and RSI/MACD warm-up periods are populated) and then trimmed to the
    requested display `period`."""
    if period not in _VALID_HISTORY_PERIODS:
        period = "6mo"
    t = yf.Ticker(symbol)
    calc_hist = t.history(period="1y" if period in {"1mo", "3mo", "6mo", "1y"} else "2y")
    if calc_hist.empty:
        return []

    closes = calc_hist["Close"]
    sma20 = closes.rolling(20).mean()
    sma50 = closes.rolling(50).mean()
    sma200 = closes.rolling(200).mean()
    rsi14 = _rsi(closes)
    _, _, macd_hist = _macd(closes)

    display_hist = calc_hist if period == "1y" or period == "2y" else t.history(period=period)
    display_dates = set(display_hist.index)

    points = []
    for date in calc_hist.index:
        if date not in display_dates:
            continue
        i = calc_hist.index.get_loc(date)
        points.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "close": _round(closes.iloc[i], 5),
                "sma20": _round(sma20.iloc[i], 5),
                "sma50": _round(sma50.iloc[i], 5),
                "sma200": _round(sma200.iloc[i], 5) if i >= 199 else None,
                "rsi14": _round(rsi14.iloc[i], 1),
                "macd_hist": _round(macd_hist.iloc[i], 6),
            }
        )
    return points


# ---- concern flags (technical caution rules) ----


def _rules():
    return [
        (
            "overbought_rsi",
            lambda s: s["rsi14"] is not None and s["rsi14"] > 70,
            "medium",
            lambda s: f"RSI(14) is overbought at {s['rsi14']}.",
        ),
        (
            "oversold_rsi",
            lambda s: s["rsi14"] is not None and s["rsi14"] < 30,
            "medium",
            lambda s: f"RSI(14) is oversold at {s['rsi14']}.",
        ),
        (
            "below_200sma",
            lambda s: s["sma200"] is not None and s["price"] is not None and s["price"] < s["sma200"],
            "medium",
            lambda s: "Price is below its 200-day average — longer-term trend is down.",
        ),
        (
            "near_52w_high",
            lambda s: (
                s["price"] and s["52w_high"] and s["52w_low"]
                and (s["52w_high"] - s["price"]) / max(s["52w_high"] - s["52w_low"], 1e-9) < 0.05
            ),
            "low",
            lambda s: f"Price is within 5% of its 52-week high ({s['52w_high']}) — limited room before prior resistance.",
        ),
        (
            "near_52w_low",
            lambda s: (
                s["price"] and s["52w_high"] and s["52w_low"]
                and (s["price"] - s["52w_low"]) / max(s["52w_high"] - s["52w_low"], 1e-9) < 0.05
            ),
            "medium",
            lambda s: f"Price is within 5% of its 52-week low ({s['52w_low']}) — trend risk if support breaks.",
        ),
        (
            "high_volatility",
            lambda s: s["atr_pct"] is not None and s["atr_pct"] > 1.2,
            "medium",
            lambda s: f"Daily ATR is elevated at {s['atr_pct']}% of price — size positions and stops accordingly.",
        ),
        (
            "bearish_macd_cross",
            lambda s: (
                s["macd_hist"] is not None and s["macd_hist_prev"] is not None
                and s["macd_hist"] < 0 and s["macd_hist_prev"] >= 0
            ),
            "low",
            lambda s: "MACD histogram just turned negative — momentum crossing bearish.",
        ),
    ]


def flag_concerns(snapshot: dict) -> list[dict]:
    concerns = []
    for rule_id, cond, severity, msg in _rules():
        try:
            if cond(snapshot):
                concerns.append({"id": rule_id, "severity": severity, "message": msg(snapshot)})
        except Exception:
            continue
    order = {"high": 0, "medium": 1, "low": 2}
    concerns.sort(key=lambda c: order.get(c["severity"], 3))
    return concerns


# ---- recommendation: trend + momentum composite score ----


def build_recommendation(snapshot: dict) -> dict:
    """Transparent Buy/Hold/Sell technical screen. Six binary checks (trend:
    price vs SMA50, price vs SMA200, SMA50 vs SMA200; momentum: RSI50-line,
    MACD line vs signal) each contribute +/-1 to a score from -5 to +5 — no
    single indicator can dominate the call, and every contributor is named in
    the reasoning. Not personalized trading advice."""
    s = snapshot
    price = s.get("price")
    reasoning = []
    score = 0

    def add(cond_true, weight, true_text, false_text):
        nonlocal score
        if cond_true is None:
            return
        if cond_true:
            score += weight
            reasoning.append(true_text)
        else:
            score -= weight
            reasoning.append(false_text)

    if price is not None and s.get("sma50") is not None:
        add(price > s["sma50"], 1, f"Price ({price}) is above SMA50 ({s['sma50']}).", f"Price ({price}) is below SMA50 ({s['sma50']}).")
    if price is not None and s.get("sma200") is not None:
        add(price > s["sma200"], 1, f"Price is above SMA200 ({s['sma200']}) — longer-term uptrend.", f"Price is below SMA200 ({s['sma200']}) — longer-term downtrend.")
    if s.get("sma50") is not None and s.get("sma200") is not None:
        add(s["sma50"] > s["sma200"], 1, "SMA50 is above SMA200 (bullish moving-average alignment).", "SMA50 is below SMA200 (bearish moving-average alignment).")
    if s.get("rsi14") is not None:
        add(s["rsi14"] > 50, 1, f"RSI(14) at {s['rsi14']} is above the 50 midline.", f"RSI(14) at {s['rsi14']} is below the 50 midline.")
    if s.get("macd_line") is not None and s.get("macd_signal") is not None:
        add(s["macd_line"] > s["macd_signal"], 1, "MACD line is above its signal line (bullish).", "MACD line is below its signal line (bearish).")

    if score >= 3:
        label = "Buy"
    elif score <= -3:
        label = "Sell"
    else:
        label = "Hold"

    return {
        "label": label,
        "score": score,
        "reasoning": reasoning,
        "disclaimer": (
            "Rule-based technical screen combining trend (SMA50/SMA200 alignment) and momentum "
            "(RSI, MACD) into a single -5..+5 score — not personalized trading advice. FX moves on "
            "macro/rate-decision catalysts this scan does not see; verify against the calendar and "
            "your own thesis before acting."
        ),
    }


