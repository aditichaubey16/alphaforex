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
  uses for equities. `backend/market_data.py` caches each function's result
  in-process — snapshots (price + indicators) for 30s, history/chart series
  for 300s — so concurrent viewers looking at the same pair within that
  window share one upstream call instead of one each. This is what protects
  against the Yahoo per-IP rate limit AlphaDesk hit on Render once it had
  real traffic (see its README).
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

Two independent paths run the same job — `backend/capture.py`'s
`run_capture()` — depending on whether you're running locally or deployed:

**Local install** — `backend/tools/capture_open_rates.py` fetches a live
price for every tracked pair and stores it as that IST calendar day's
"open" (upsert — re-running the same day overwrites, so it's safe to run
more than once). A Windows Scheduled Task named **"AlphaForex Daily Open
Capture"** runs it automatically every day at 10:00 (the machine this was
set up on is already on IST, so no timezone offset was needed — confirm
yours is too, or adjust the trigger time in Task Scheduler). A local
machine has to actually be on and awake at 10:00 for this to fire —
if it's asleep, Task Scheduler's catch-up (`-StartWhenAvailable`) runs it
late, and if the machine is off across multiple mornings, those days are
simply missed. That unreliability is the whole reason the deployed path
below exists.

To recreate the task on another machine:

```powershell
$pythonExe = "<path-to-alphaforex>\venv\Scripts\python.exe"
$workDir = "<path-to-alphaforex>"
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "-m backend.tools.capture_open_rates" -WorkingDirectory $workDir
$trigger = New-ScheduledTaskTrigger -Daily -At 10:00AM
Register-ScheduledTask -TaskName "AlphaForex Daily Open Capture" -Action $action -Trigger $trigger -Description "Captures today's opening rate for every AlphaForex tracked pair at 10:00 IST."
```

**Deployed (Render)** — there's no machine of yours that needs to be
awake. A protected endpoint, `POST /api/admin/capture-open-rates`, runs the
same capture over HTTP, gated on an `X-Capture-Secret` header matching the
`ALPHAFOREX_CAPTURE_SECRET` env var (the endpoint refuses every request if
that env var isn't set — no accidental "open" mode). A free GitHub Actions
scheduled workflow, `.github/workflows/daily-open-capture.yml`, calls it
daily at 04:30 UTC (10:00 IST) — see "Deploying to Render" below for setup.
Render's own Cron Jobs were the more obvious choice but aren't on the free
plan (minimum $1/mo), so this app doesn't use one.

## Deploying to Render

```bash
git push  # if you haven't already
```

Then on [Render](https://dashboard.render.com): **New > Blueprint**, connect
the `alphaforex` GitHub repo, and it picks up `render.yaml` automatically —
one free web service, no cron job (see above for why). Render will prompt
for the one `sync: false` env var during setup:

- `ALPHAFOREX_CAPTURE_SECRET` — any random string; it just has to match the
  same-named secret on the GitHub Actions side (see below).

Once deployed, wire up the GitHub Actions side (Settings > Secrets and
variables > Actions on the repo):

- **Secret** `ALPHAFOREX_CAPTURE_SECRET` — the exact same value you set on
  Render.
- **Variable** `ALPHAFOREX_APP_URL` — the deployed app's URL (Render tells
  you this after the first deploy — usually `https://alphaforex.onrender.com`
  unless that subdomain was taken, in which case Render appends a suffix and
  you'll need to update this variable to match).

The workflow also has a manual trigger (`workflow_dispatch`) from the
Actions tab if a morning gets missed and you don't want to wait for the
next scheduled run.

Free-tier Render services spin down after 15 minutes idle and take ~30-60s
to wake on the next request — the first visitor of the day eats that cold
start. AlphaDesk's README notes the same tradeoff and its git history has a
keep-alive-ping commit if this becomes annoying enough to fix the same way.

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
- The *local* scheduled capture task only runs while the machine is on; if
  it's asleep or off at 10:00, Task Scheduler runs it late
  (`-StartWhenAvailable`) or not at all that day. This doesn't affect the
  deployed Render instance, which uses the GitHub Actions path instead (see
  "Morning rate capture" above) — no local machine involved.
- Render's free tier spins the service down after 15 minutes idle; the
  first request after that pays a ~30-60s cold-start cost. The GitHub
  Actions capture ping itself will wake it if it's the first hit of the
  morning.
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
