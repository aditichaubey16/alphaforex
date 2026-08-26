"""One-time bulk import of the 2026 central-bank calendar into the events
table. Run once after a fresh install (or whenever `data/economic_calendar_2026.json`
is updated) —

    venv\\Scripts\\python.exe -m backend.tools.load_2026_calendar

Idempotent: skips any (currency, date, event_type) already in the database,
so re-running after editing the JSON only adds what's new.

Source: each currency's own central bank — Federal Reserve, ECB, Bank of
England, Bank of Japan, Reserve Bank of Australia, Bank of Canada, Reserve
Bank of New Zealand, Swiss National Bank, and the Reserve Bank of India —
compiled from their published 2026 meeting schedules as of the import date.
Central banks occasionally amend schedules; two SNB dates are marked
"estimated" in their description because SNB had not yet published its
H2 2026 calendar at compile time. See each event's `source` field.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend import db

_CALENDAR_PATH = Path(__file__).parent.parent / "data" / "economic_calendar_2026.json"


def main() -> None:
    db.init_db()
    events = json.loads(_CALENDAR_PATH.read_text(encoding="utf-8"))
    added, skipped = 0, 0
    for e in events:
        if db.event_exists(e["currency"], e["event_date"], e["event_type"]):
            skipped += 1
            continue
        db.add_event(None, e["currency"], e["event_type"], e["event_date"], e.get("description"), e.get("source"))
        added += 1
    print(f"[load_2026_calendar] {added} events added, {skipped} already present (skipped).")


if __name__ == "__main__":
    main()
