import httpx
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF"
GOLD_API_URL = "https://api.gold-api.com/price/XAU"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def is_market_closed() -> bool:
    now = datetime.now(timezone.utc)
    return now.weekday() >= 5

async def fetch_prices() -> list[float] | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(COINGECKO_URL, params={
                "vs_currency": "usd", "days": 7
            }, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            prices = [p[1] for p in data["prices"]]
            sampled = prices[::6]
            logger.info(f"Fetched {len(sampled)} hourly samples for BTC")
            return sampled
    except Exception as e:
        logger.error(f"Failed BTC fetch: {e}")
        return None

async def fetch_gold_prices() -> list[float] | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(YAHOO_URL, params={
                "interval": "1h", "range": "7d",
            }, headers=YAHOO_HEADERS, timeout=10, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
            quotes = data["chart"]["result"][0]["indicators"]["quote"][0]
            closes = [c for c in quotes["close"] if c]
            return closes
    except Exception as e:
        logger.error(f"Failed gold fetch: {e}")
        return None

async def fetch_gold_spot() -> float | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(GOLD_API_URL, timeout=10)
            resp.raise_for_status()
            return resp.json()["price"]
    except Exception as e:
        logger.warning(f"Failed gold spot: {e}")
        return None

def calc_rsi(prices: list[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains, losses = 0, 0
    for i in range(-period, 0):
        diff = prices[i] - prices[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calc_ma(prices: list[float], period: int) -> float:
    if len(prices) < period:
        return prices[-1]
    return round(sum(prices[-period:]) / period, 2)

def analyze_prices(closes: list[float], spot: float | None = None) -> dict:
    current_price = spot or closes[-1]

    rsi = calc_rsi(closes, 14)
    ma9 = calc_ma(closes, 9)
    ma21 = calc_ma(closes, 21)
    ma50 = calc_ma(closes, 50)

    prev_ma9 = calc_ma(closes[:-1], 9)
    prev_ma21 = calc_ma(closes[:-1], 21)

    signals = []
    confidence = "MEDIUM"
    reason = []

    if rsi < 30:
        signals.append("BUY")
        confidence = "HIGH"
        reason.append(f"RSI oversold ({rsi})")
    elif rsi > 70:
        signals.append("SELL")
        confidence = "HIGH"
        reason.append(f"RSI overbought ({rsi})")

    if prev_ma9 <= prev_ma21 and ma9 > ma21:
        signals.append("BUY")
        reason.append("MA9 crossed above MA21 (Golden Cross)")
    elif prev_ma9 >= prev_ma21 and ma9 < ma21:
        signals.append("SELL")
        reason.append("MA9 crossed below MA21 (Death Cross)")

    direction = "NEUTRAL"
    buy_count = signals.count("BUY")
    sell_count = signals.count("SELL")

    if buy_count > sell_count:
        direction = "BUY"
        confidence = "HIGH" if buy_count >= 2 else "MEDIUM"
    elif sell_count > buy_count:
        direction = "SELL"
        confidence = "HIGH" if sell_count >= 2 else "MEDIUM"

    if not reason:
        if 40 <= rsi <= 60:
            reason.append("Market neutral")
            confidence = "LOW"
        elif rsi < 45:
            reason.append(f"RSI bearish ({rsi})")
            direction = "SELL"
            confidence = "MEDIUM"
        elif rsi > 55:
            reason.append(f"RSI bullish ({rsi})")
            direction = "BUY"
            confidence = "MEDIUM"

    entry = current_price
    if direction == "BUY":
        sl = round(entry * 0.98, 2)
        tp = round(entry * 1.04, 2)
    elif direction == "SELL":
        sl = round(entry * 1.02, 2)
        tp = round(entry * 0.96, 2)
    else:
        sl = round(entry * 0.99, 2)
        tp = round(entry * 1.01, 2)

    return {
        "price": current_price,
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "confidence": confidence,
        "rsi": rsi,
        "ma9": ma9,
        "ma21": ma21,
        "ma50": ma50,
        "reason": "; ".join(reason),
    }

async def analyze() -> dict:
    closes = await fetch_prices()
    if not closes:
        return {"error": "Cannot fetch BTC market data"}
    return analyze_prices(closes)

async def analyze_gold() -> dict:
    closes = await fetch_gold_prices()
    spot = await fetch_gold_spot()

    if not closes:
        return {"error": "Cannot fetch XAUUSD market data", "spot": spot}

    result = analyze_prices(closes, spot)
    if is_market_closed():
        result["market"] = "CLOSED (weekend)"
    else:
        result["market"] = "OPEN"
    return result
