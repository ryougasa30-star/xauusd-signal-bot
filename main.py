import uuid
import hmac
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import SIGNAL_INTERVAL_MINUTES, WEBHOOK_SECRET, TV_TICKER
from models import Signal, DropSignalRequest, ConfigUpdate, resolve_tv_field
from signal_generator import generate_signal, generate_price
import telegram_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
signals_db: list[Signal] = []

def parse_tv_payload(data: dict[str, Any]) -> Signal | None:
    pair = resolve_tv_field(data, "pair") or TV_TICKER
    direction = resolve_tv_field(data, "direction")
    entry = resolve_tv_field(data, "entry_price")
    sl = resolve_tv_field(data, "stop_loss")
    tp = resolve_tv_field(data, "take_profit")
    confidence = resolve_tv_field(data, "confidence") or "MEDIUM"
    strategy = resolve_tv_field(data, "strategy") or "TradingView Alert"
    notes = resolve_tv_field(data, "notes")

    if not direction or entry is None:
        logger.warning(f"TradingView payload missing direction/entry: {data}")
        return None

    direction = str(direction).upper()
    if direction not in ("BUY", "SELL", "LONG", "SHORT"):
        direction = "BUY" if direction in ("buy", "long", "bull") else "SELL"

    if direction in ("LONG",):
        direction = "BUY"
    elif direction in ("SHORT",):
        direction = "SELL"

    try:
        entry = float(entry)
    except (TypeError, ValueError):
        return None

    sl = float(sl) if sl else round(entry - 20 if direction == "BUY" else entry + 20, 2)
    tp = float(tp) if tp else round(entry + 30 if direction == "BUY" else entry - 30, 2)

    return Signal(
        id=uuid.uuid4().hex[:8].upper(),
        pair=str(pair).upper(),
        direction=direction,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        confidence=str(confidence).upper(),
        timestamp=datetime.now(timezone.utc),
        strategy=str(strategy),
        notes=str(notes) if notes else None,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    telegram_bot.configure()
    if SIGNAL_INTERVAL_MINUTES > 0:
        scheduler.add_job(auto_drop_signal, "interval", minutes=SIGNAL_INTERVAL_MINUTES)
        scheduler.start()
    yield
    scheduler.shutdown(wait=False)

app = FastAPI(title="BTCUSDM Signal Bot", version="2.0.0", lifespan=lifespan)

async def auto_drop_signal():
    signal = generate_signal()
    signals_db.append(signal)
    await telegram_bot.send_signal(signal)

@app.get("/")
def root():
    return {"status": "running", "pair": "BTCUSDM", "signals_dropped": len(signals_db), "mode": "TradingView Webhook" if WEBHOOK_SECRET else "Simulated"}

@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request):
    body = await request.json()

    if WEBHOOK_SECRET:
        token = request.headers.get("x-webhook-secret") or request.headers.get("authorization", "").replace("Bearer ", "")
        if not hmac.compare_digest(token, WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    signal = parse_tv_payload(body)
    if not signal:
        raise HTTPException(status_code=400, detail="Invalid payload: direction and entry_price required")

    signals_db.append(signal)
    ok = await telegram_bot.send_signal(signal)
    logger.info(f"Webhook signal {signal.id} - {signal.direction} @ {signal.entry_price} (sent={ok})")
    return {"status": "received", "signal_id": signal.id, "telegram_sent": ok}

@app.get("/signals", response_model=list[Signal])
def list_signals(limit: int = 20):
    return sorted(signals_db, key=lambda s: s.timestamp, reverse=True)[:limit]

@app.post("/signal/drop", response_model=Signal)
async def drop_signal(req: DropSignalRequest = None):
    if req and req.direction:
        signal = Signal(
            id=uuid.uuid4().hex[:8].upper(),
            pair="BTCUSDM",
            direction=req.direction.upper(),
            entry_price=req.entry_price or generate_price(),
            stop_loss=req.stop_loss or 0.0,
            take_profit=req.take_profit or 0.0,
            confidence=req.confidence or "MEDIUM",
            timestamp=datetime.now(timezone.utc),
            strategy="Manual",
            notes=req.notes,
        )
    else:
        signal = generate_signal()

    signals_db.append(signal)
    ok = await telegram_bot.send_signal(signal)
    return signal

@app.post("/config")
def update_config(cfg: ConfigUpdate):
    telegram_bot.configure(cfg.telegram_bot_token, cfg.telegram_chat_id)
    if cfg.interval_minutes:
        scheduler.reschedule_job("interval", trigger="interval", minutes=cfg.interval_minutes)
    return {"configured": True}

@app.get("/health")
def health():
    return {"status": "ok", "signals": len(signals_db), "telegram_configured": telegram_bot._forward_url is not None}
