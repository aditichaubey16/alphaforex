"""IST date/time helpers. The "opening rate" concept is anchored to the IST
trading day regardless of what timezone the machine running the app (or the
capture script) is actually in."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def ist_now() -> datetime:
    return datetime.now(IST)


def ist_today_str() -> str:
    return ist_now().strftime("%Y-%m-%d")
