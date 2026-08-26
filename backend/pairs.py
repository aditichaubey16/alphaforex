"""The tracked universe: majors + INR crosses. Fixed and small (unlike
AlphaDesk's 2,500-name NSE directory), so there's no search-to-add step —
the app shows every tracked pair directly on open. yfinance ticker
convention: `{BASE}{QUOTE}=X`.
"""
from __future__ import annotations

# 7 most-traded pairs — deep liquidity, reliable yfinance coverage.
MAJORS = [
    {"symbol": "EURUSD=X", "base": "EUR", "quote": "USD", "name": "Euro / US Dollar"},
    {"symbol": "GBPUSD=X", "base": "GBP", "quote": "USD", "name": "British Pound / US Dollar"},
    {"symbol": "USDJPY=X", "base": "USD", "quote": "JPY", "name": "US Dollar / Japanese Yen"},
    {"symbol": "USDCHF=X", "base": "USD", "quote": "CHF", "name": "US Dollar / Swiss Franc"},
    {"symbol": "USDCAD=X", "base": "USD", "quote": "CAD", "name": "US Dollar / Canadian Dollar"},
    {"symbol": "AUDUSD=X", "base": "AUD", "quote": "USD", "name": "Australian Dollar / US Dollar"},
    {"symbol": "NZDUSD=X", "base": "NZD", "quote": "USD", "name": "New Zealand Dollar / US Dollar"},
]

# INR crosses — relevant for an India-based analyst tracking the rupee
# against each major. Coverage on Yahoo varies by cross; a pair that returns
# no data just shows "no data" in the UI rather than breaking the app.
INR_CROSSES = [
    {"symbol": "USDINR=X", "base": "USD", "quote": "INR", "name": "US Dollar / Indian Rupee"},
    {"symbol": "EURINR=X", "base": "EUR", "quote": "INR", "name": "Euro / Indian Rupee"},
    {"symbol": "GBPINR=X", "base": "GBP", "quote": "INR", "name": "British Pound / Indian Rupee"},
    {"symbol": "JPYINR=X", "base": "JPY", "quote": "INR", "name": "Japanese Yen / Indian Rupee"},
    {"symbol": "CHFINR=X", "base": "CHF", "quote": "INR", "name": "Swiss Franc / Indian Rupee"},
    {"symbol": "CADINR=X", "base": "CAD", "quote": "INR", "name": "Canadian Dollar / Indian Rupee"},
    {"symbol": "AUDINR=X", "base": "AUD", "quote": "INR", "name": "Australian Dollar / Indian Rupee"},
]

GROUPS = [("Majors", MAJORS), ("INR Crosses", INR_CROSSES)]


def list_all() -> list[dict]:
    out = []
    for group_name, pairs in GROUPS:
        for p in pairs:
            out.append({**p, "group": group_name})
    return out


_BY_SYMBOL = {p["symbol"]: p for p in list_all()}


def find(symbol: str) -> dict | None:
    return _BY_SYMBOL.get(symbol.upper())


def is_tracked(symbol: str) -> bool:
    return symbol.upper() in _BY_SYMBOL
