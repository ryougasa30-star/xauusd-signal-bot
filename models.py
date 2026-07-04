from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any

class Signal(BaseModel):
    id: str
    pair: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: str = "MEDIUM"
    timestamp: datetime
    strategy: str = "TradingView Alert"
    notes: Optional[str] = None

class DropSignalRequest(BaseModel):
    direction: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: Optional[str] = "MEDIUM"
    notes: Optional[str] = None

class ConfigUpdate(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    interval_minutes: Optional[int] = None

TV_FIELD_ALIASES = {
    "pair": ["pair", "symbol", "ticker", "market", "instrument"],
    "direction": ["direction", "side", "signal", "action", "type", "order_type"],
    "entry_price": ["entry_price", "entry", "price", "open_price", "enter", "entryprice"],
    "stop_loss": ["stop_loss", "sl", "stoploss", "stop", "stop_loss_price"],
    "take_profit": ["take_profit", "tp", "takeprofit", "target", "profit", "takeprofit"],
    "confidence": ["confidence", "confidence_level", "prob", "probability", "strength"],
    "strategy": ["strategy", "strategy_name", "alert_name", "name"],
    "notes": ["notes", "comment", "note", "description", "message", "alert_message"],
}

def resolve_tv_field(data: dict[str, Any], field: str) -> Any:
    for alias in TV_FIELD_ALIASES.get(field, [field]):
        if alias in data:
            return data[alias]
        lower_alias = alias.lower()
        if lower_alias in data:
            return data[lower_alias]
    return None
