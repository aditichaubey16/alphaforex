"""AlphaForex FastAPI app: JSON API + static frontend."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, market_data, pairs, timeutil

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "static"
_ASSET_VERSION = str(int(time.time()))

app = FastAPI(title="AlphaForex")


@app.on_event("startup")
def _startup():
    db.init_db()


def _pair_or_404(symbol: str) -> dict:
    p = pairs.find(symbol)
    if not p:
        raise HTTPException(status_code=404, detail=f"{symbol} is not a tracked pair")
    return p


# ---- tracked pairs ----

@app.get("/api/pairs")
def get_pairs():
    return pairs.list_all()


# ---- data export (backup) ----

@app.get("/api/export")
def export_data():
    data = db.export_all()
    filename = f"alphaforex-backup-{db.now()[:10]}.json"
    return JSONResponse(content=data, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ---- pair research page ----

@app.get("/api/pair/{symbol}")
def get_pair_snapshot(symbol: str):
    p = _pair_or_404(symbol)
    try:
        snapshot = market_data.fetch_snapshot(p["symbol"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch live data: {e}")

    today_open = db.get_daily_open(p["symbol"], timeutil.ist_today_str())
    open_rate = today_open["open_rate"] if today_open else None
    snapshot["open_today"] = open_rate
    snapshot["change_from_open_pct"] = (
        round((snapshot["price"] - open_rate) / open_rate * 100, 2)
        if open_rate and snapshot.get("price") is not None
        else None
    )

    concerns = market_data.flag_concerns(snapshot)
    recommendation = market_data.build_recommendation(snapshot)
    calendar = db.list_events_for_currencies([p["base"], p["quote"]], timeutil.ist_today_str())
    return {"pair": p, "snapshot": snapshot, "concerns": concerns, "recommendation": recommendation, "calendar": calendar}


@app.get("/api/pair/{symbol}/history")
def get_pair_history(symbol: str, period: str = "6mo"):
    p = _pair_or_404(symbol)
    try:
        return market_data.fetch_price_history(p["symbol"], period)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch price history: {e}")


@app.get("/api/pair/{symbol}/indicators-history")
def get_pair_indicators_history(symbol: str, period: str = "6mo"):
    p = _pair_or_404(symbol)
    try:
        return market_data.fetch_indicator_history(p["symbol"], period)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch indicator history: {e}")


@app.get("/api/opens/today")
def get_todays_opens():
    """{symbol: open_rate} for every pair captured so far today (IST) — empty
    until the 10:00 IST capture job has run at least once (see
    backend/tools/capture_open_rates.py)."""
    return db.list_daily_opens(timeutil.ist_today_str())


class NoteIn(BaseModel):
    body: str


@app.get("/api/pair/{symbol}/notes")
def get_notes(symbol: str):
    p = _pair_or_404(symbol)
    return db.list_notes(p["symbol"])


@app.post("/api/pair/{symbol}/notes")
def post_note(symbol: str, note: NoteIn):
    p = _pair_or_404(symbol)
    return db.add_note(p["symbol"], note.body)


class ThesisIn(BaseModel):
    thesis_text: str = ""
    risks: str = ""
    catalysts: str = ""


@app.get("/api/pair/{symbol}/thesis")
def get_thesis(symbol: str):
    p = _pair_or_404(symbol)
    thesis = db.get_thesis(p["symbol"])
    return thesis or {"thesis_text": "", "risks": "", "catalysts": ""}


@app.put("/api/pair/{symbol}/thesis")
def put_thesis(symbol: str, thesis: ThesisIn):
    p = _pair_or_404(symbol)
    return db.upsert_thesis(p["symbol"], thesis.thesis_text, thesis.risks, thesis.catalysts)


class ForecastIn(BaseModel):
    period_label: str
    est_level: float | None = None


@app.get("/api/pair/{symbol}/forecasts")
def get_forecasts(symbol: str):
    p = _pair_or_404(symbol)
    return db.list_forecasts(p["symbol"])


@app.post("/api/pair/{symbol}/forecasts")
def post_forecast(symbol: str, forecast: ForecastIn):
    p = _pair_or_404(symbol)
    return db.add_forecast(p["symbol"], forecast.period_label, forecast.est_level)


class ForecastActualIn(BaseModel):
    actual_level: float | None = None


@app.put("/api/forecasts/{forecast_id}/actual")
def put_forecast_actual(forecast_id: int, actual: ForecastActualIn):
    result = db.update_forecast_actual(forecast_id, actual.actual_level)
    if not result:
        raise HTTPException(status_code=404, detail="Forecast not found")
    return result


# ---- calendar / events ----

@app.get("/api/events")
def get_events():
    return db.list_events()


class EventIn(BaseModel):
    symbol: str | None = None
    currency: str | None = None
    event_type: str
    event_date: str
    description: str | None = None


@app.post("/api/events")
def post_event(event: EventIn):
    symbol = None
    if event.symbol:
        p = _pair_or_404(event.symbol)
        symbol = p["symbol"]
    return db.add_event(symbol, event.currency, event.event_type, event.event_date, event.description, source="manual")


# ---- frontend ----

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("style.css", f"style.css?v={_ASSET_VERSION}")
    html = html.replace("app.js", f"app.js?v={_ASSET_VERSION}")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})
