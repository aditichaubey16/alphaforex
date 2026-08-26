# AlphaForex

A live FX research workspace: technical screens on the 7 major currency
pairs plus 7 INR crosses, daily opening rates captured every morning, and a
2026 central-bank calendar — backed by a real SQLite database.

Sibling to `../alphadesk` (equity research) — separate folder, separate
venv, separate database (`alphaforex.sqlite3`), separate port (8020 vs
AlphaDesk's 8010). It reuses AlphaDesk's *patterns* (FastAPI + SQLite +
vanilla JS layout) but shares no code, imports, or runtime state.

No accounts, no login — open it and you're straight into the app.

## Why technical, not fundamental

A currency pair has no P/E, ROE, or earnings — equity research's usual
toolkit doesn't apply. Every signal here comes from price action instead:
moving averages (SMA20/50/200), momentum (RSI14, MACD), and volatility (ATR).
The Buy/Hold/Sell call is a transparent -5..+5 score built from five named
checks (see "How the call works" below) — nothing is inferred by a model.

## Run it

```bash
cd alphaforex
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python app.py
```

Opens `http://127.0.0.1:8020` in your browser automatically.

## What's here

- **Market** — two tiles, Majors and INR Crosses. Each opens a market-watch
  table (Pair · Open · High · Low · Last · Chg % · Call) — a live rate feed
  and the rule-based technical call for every tracked pair, no search-to-add
  step needed since the universe is fixed and small.
- **Pair research page** — live snapshot (price, today's open and change
  since open, day/week/month change, RSI14, ATR14, 52-week range), one
  price chart with an SMA20/50/200 trend overlay, rule-based concern flags,
  a transparent recommendation banner, a currency calendar (this pair's
  base and quote currency's upcoming central-bank events), notes
  (append-only log), thesis/risks/catalysts, and a forecast-vs-actual level
  tracker.
- **Calendar** — the full 2026 central-bank calendar (60 rate-decision
  events across all 9 tracked currencies), filterable by currency, plus your
  own manually-added events (optionally tagged to a pair or a currency).

Data lives in `alphaforex.sqlite3` in this folder — nothing leaves your
machine except live `yfinance` lookups.

## Data sources

- **Live rates**: `yfinance` (Yahoo Finance) — the same source AlphaDesk
  uses for equities. Every pair's price, OHLC, and history come from one
  live call per request; nothing is scraped or cached beyond the in-process
  TTLs noted below.
- **Daily opening rate**: captured once a day by
  `backend/tools/capture_open_rates.py` — see "Morning rate capture" below.
- **2026 central-bank calendar**: compiled from each bank's own published
  schedule (federalreserve.gov, ecb.europa.eu, bankofengland.co.uk,
  boj.or.jp, rba.gov.au, bankofcanada.ca, rbnz.govt.nz, snb.ch, rbi.org.in)
  — see `backend/data/economic_calendar_2026.json` for the full dataset with
  a `source` field on every row. Two SNB 2026 dates (Sep/Dec) are marked
  "estimated" because SNB hadn't published its H2 schedule at compile time.

## How the call works

Five checks, each worth +1/-1, summed into a score from -5 to +5:

1. Price vs SMA50
2. Price vs SMA200
3. SMA50 vs SMA200 (golden/death cross state)
4. RSI14 vs the 50 midline
5. MACD line vs its signal line

Score ≥ +3 is a **Buy**, ≤ -3 is a **Sell**, anything in between is a
**Hold**. Concern flags (overbought/oversold RSI, below-200-SMA, near
52-week high/low, elevated ATR, a fresh bearish MACD cross) are shown
separately as named risk callouts — they don't move the label, they're
context for it.

## Morning rate capture (10:00 IST)

`backend/tools/capture_open_rates.py` fetches a live price for every
tracked pair and stores it as that IST calendar day's "open" (upsert —
re-running the same day overwrites, so it's safe to run more than once).
A Windows Scheduled Task named **"AlphaForex Daily Open Capture"** runs it
automatically every day at 10:00 (the machine this was set up on is already
on IST, so no timezone offset was needed — confirm yours is too, or adjust
the trigger time in Task Scheduler).

To recreate the task on another machine:

```powershell
$pythonExe = "<path-to-alphaforex>\venv\Scripts\python.exe"
$workDir = "<path-to-alphaforex>"
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "-m backend.tools.capture_open_rates" -WorkingDirectory $workDir
$trigger = New-ScheduledTaskTrigger -Daily -At 10:00AM
Register-ScheduledTask -TaskName "AlphaForex Daily Open Capture" -Action $action -Trigger $trigger -Description "Captures today's opening rate for every AlphaForex tracked pair at 10:00 IST."
```

## Loading the 2026 calendar

Run once after a fresh install (idempotent — safe to re-run):

```bash
venv\Scripts\python.exe -m backend.tools.load_2026_calendar
```

## Known limitations

- RSI here uses a plain rolling average, not Wilder's smoothing — easier to
  audit, slightly different from what most charting platforms show.
- INR-cross coverage on Yahoo Finance varies — a pair that returns no data
  shows "no data" in the UI rather than breaking the app (`AUDINR=X`,
  `CHFINR=X`, `CADINR=X` are the thinner-traded crosses most likely to lag).
- No interest-rate-differential (carry) signal — deliberately technical-only
  for this version.
- The scheduled capture task only runs while the machine is on; if it's
  asleep or off at 10:00 the task is configured to run at the next
  opportunity (`-StartWhenAvailable`), not exactly at 10:00.
- Notes are an append-only log rather than true diff-based version history.
- Runs locally over plain HTTP — fine on `localhost`, not meant to be
  exposed beyond that without HTTPS in front of it.
- Schema is plain SQLite via stdlib `sqlite3`, no ORM.
- Single-user, no accounts — see "Phase 2 ideas".

## Phase 2 ideas (not built yet)

- Multi-user accounts — same lightweight name+email model as AlphaDesk, if
  this gets shared beyond one person
- Interest-rate-differential / carry-trade overlay
- Position tracking with P&L (removed from this version to keep the
  GitHub-published scope focused on the research/calendar workflow — see
  git history in `../alphadesk` for the equivalent pattern if resurrecting
  this)
- Compare view (side-by-side technicals for up to 4 pairs)

---

Built by **Aditi Chaubey** — CA, 5+ years across Forex Trading, Accounting,
Finance, Equity Research, and Automation.
