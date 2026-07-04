import random
import uuid
from datetime import datetime, timezone
from models import Signal

BASE_PRICE = 65000.0
PRICE_RANGE = 3000.0

STRATEGIES = [
    "RSI Divergence",
    "MA Crossover",
    "Bollinger Bands Squeeze",
    "Support/Resistance Breakout",
    "MACD Bullish Cross",
    "Fibonacci Retracement",
]

def generate_price(base: float = BASE_PRICE) -> float:
    jitter = random.uniform(-PRICE_RANGE, PRICE_RANGE)
    return round(base + jitter, 2)

def generate_signal(pair: str = "BTCUSDM") -> Signal:
    direction = random.choice(["BUY", "SELL"])
    entry = generate_price()
    spread = random.uniform(10, 40)
    tp_multiplier = random.uniform(1.5, 3.0)
    sl_multiplier = random.uniform(0.5, 1.2)

    if direction == "BUY":
        sl = round(entry - spread * sl_multiplier, 2)
        tp = round(entry + spread * tp_multiplier, 2)
    else:
        sl = round(entry + spread * sl_multiplier, 2)
        tp = round(entry - spread * tp_multiplier, 2)

    confidence = random.choices(
        ["HIGH", "MEDIUM", "LOW"], weights=[30, 50, 20], k=1
    )[0]

    return Signal(
        id=uuid.uuid4().hex[:8].upper(),
        pair=pair,
        direction=direction,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        confidence=confidence,
        timestamp=datetime.now(timezone.utc),
        strategy=random.choice(STRATEGIES),
    )
