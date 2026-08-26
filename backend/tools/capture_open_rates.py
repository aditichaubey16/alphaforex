"""Captures today's (IST calendar day) opening rate for every tracked pair.

Run daily, once, ideally right around market open —

    venv\\Scripts\\python.exe -m backend.tools.capture_open_rates

A live price fetched at any point in the day is used as that day's "open" —
FX doesn't have a single exchange-defined open the way an equity does, so
this is simply "first rate captured today." Re-running later the same IST
day overwrites the earlier value (see the ON CONFLICT upsert in db.py), so
schedule it once, early, and leave it alone — see README.md for the Windows
Task Scheduler setup that runs this at 10:00 IST.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend import db, market_data, pairs, timeutil


def main() -> None:
    db.init_db()
    trade_date = timeutil.ist_today_str()
    ok, failed = 0, 0
    for p in pairs.list_all():
        symbol = p["symbol"]
        try:
            snapshot = market_data.fetch_snapshot(symbol)
            price = snapshot.get("price")
            if price is None:
                raise ValueError("no price in snapshot")
            db.upsert_daily_open(symbol, trade_date, price)
            print(f"[capture_open_rates] {symbol}: {price}")
            ok += 1
        except Exception as e:
            print(f"[capture_open_rates] {symbol}: FAILED — {e}")
            failed += 1
    print(f"[capture_open_rates] done for {trade_date} — {ok} captured, {failed} failed")


if __name__ == "__main__":
    main()
