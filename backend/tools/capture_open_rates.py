"""Captures today's (IST calendar day) opening rate for every tracked pair.

Run daily, once, ideally right around market open —

    venv\\Scripts\\python.exe -m backend.tools.capture_open_rates

See README.md for the Windows Task Scheduler setup that runs this at 10:00
IST on a local install. The deployed Render instance uses a different path
for the same job — a free GitHub Actions cron hitting `POST
/api/admin/capture-open-rates` — since Render's own Cron Jobs aren't
available on the free plan. Core logic lives in `backend/capture.py`,
shared by both paths.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.capture import run_capture


def main() -> None:
    result = run_capture()
    for r in result["results"]:
        if r["ok"]:
            print(f"[capture_open_rates] {r['symbol']}: {r['price']}")
        else:
            print(f"[capture_open_rates] {r['symbol']}: FAILED — {r['error']}")
    print(f"[capture_open_rates] done for {result['trade_date']} — {result['captured']} captured, {result['failed']} failed")


if __name__ == "__main__":
    main()
