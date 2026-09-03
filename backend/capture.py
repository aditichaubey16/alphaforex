"""Shared core of the daily opening-rate capture — used by both the CLI
script (`backend/tools/capture_open_rates.py`, for a local Windows
Scheduled Task) and the protected HTTP endpoint (`POST
/api/admin/capture-open-rates`, for the free GitHub Actions cron used on
the deployed Render instance — see .github/workflows/daily-open-capture.yml).

A live price fetched at any point in the day is used as that day's "open" —
FX doesn't have a single exchange-defined open the way an equity does, so
this is simply "first rate captured today." Re-running later the same IST
day overwrites the earlier value (see the ON CONFLICT upsert in db.py), so
it's safe to trigger more than once — only the first run of the day matters.
"""
from __future__ import annotations

from . import db, market_data, pairs, timeutil


def run_capture() -> dict:
    db.init_db()
    trade_date = timeutil.ist_today_str()
    results = []
    for p in pairs.list_all():
        symbol = p["symbol"]
        try:
            snapshot = market_data.fetch_snapshot(symbol)
            price = snapshot.get("price")
            if price is None:
                raise ValueError("no price in snapshot")
            db.upsert_daily_open(symbol, trade_date, price)
            results.append({"symbol": symbol, "ok": True, "price": price})
        except Exception as e:
            results.append({"symbol": symbol, "ok": False, "error": str(e)})
    ok = sum(1 for r in results if r["ok"])
    return {"trade_date": trade_date, "captured": ok, "failed": len(results) - ok, "results": results}
