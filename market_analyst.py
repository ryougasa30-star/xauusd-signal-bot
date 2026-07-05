import feedparser
import httpx
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF"
GOLD_API_URL = "https://api.gold-api.com/price/XAU"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"
NEWS_RSS = "https://news.google.com/rss/search?q=bitcoin+cryptocurrency+blockchain&hl=en-US&gl=US&ceid=US:en"

POSITIVE_WORDS = {"bull", "bullish", "surge", "rally", "gain", "green", "moon", "pump", "breakout", "uptrend", "support", "adoption", "approval", "launch", "partnership", "upgrade", "growth", "positive", "profit", "high"}
NEGATIVE_WORDS = {"bear", "bearish", "crash", "dump", "drop", "red", "fud", "fear", "ban", "hack", "breach", "regulation", "sell-off", "decline", "loss", "negative", "low", "risk", "inflation", "war"}

def is_market_closed() -> bool:
    now = datetime.now(timezone.utc)
    return now.weekday() >= 5

async def fetch_prices() -> list[float] | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(COINGECKO_URL, params={"vs_currency": "usd", "days": 7}, timeout=10)
            resp.raise_for_status()
            prices = [p[1] for p in resp.json()["prices"]][::6]
            return prices
    except Exception as e:
        logger.error(f"Failed BTC fetch: {e}")
        return None

async def fetch_gold_prices() -> list[float] | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(YAHOO_URL, params={"interval": "1h", "range": "7d"}, headers=YAHOO_HEADERS, timeout=10, follow_redirects=True)
            resp.raise_for_status()
            closes = [c for c in resp.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
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

async def fetch_news() -> list[dict] | None:
    try:
        feed = feedparser.parse(NEWS_RSS)
        articles = []
        for entry in feed.entries[:6]:
            src = getattr(entry, "source", None)
            articles.append({
                "title": entry.get("title", ""),
                "source": src.title if src else "News",
                "url": entry.get("link", ""),
                "body": entry.get("summary", ""),
                "published": entry.get("published", ""),
            })
        return articles if articles else None
    except Exception as e:
        logger.error(f"Failed news fetch: {e}")
        return None

async def fetch_fear_greed() -> dict | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(FEAR_GREED_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()["data"][0]
            return {"value": int(data["value"]), "classification": data["value_classification"]}
    except Exception as e:
        logger.error(f"Failed fear/greed: {e}")
        return None

def analyze_sentiment(texts: list[str]) -> dict:
    pos, neg, neu = 0, 0, 0
    for text in texts:
        words = set(text.lower().split())
        pos += len(words & POSITIVE_WORDS)
        neg += len(words & NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return {"score": 0, "label": "NEUTRAL", "pos": 0, "neg": 0}
    score = round((pos - neg) / total * 100, 1)
    label = "BULLISH" if score > 15 else "BEARISH" if score < -15 else "NEUTRAL"
    return {"score": score, "label": label, "pos": pos, "neg": neg}

async def analyze_news_sentiment() -> dict:
    articles = await fetch_news()
    if not articles:
        return {"error": "Cannot fetch news"}
    texts = [a["title"] + " " + a.get("body", a.get("summary", "")) for a in articles]
    sentiment = analyze_sentiment(texts)
    sentiment["articles"] = articles
    sentiment["count"] = len(articles)
    return sentiment

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
    avg_gain, avg_loss = gains / period, losses / period
    if avg_loss == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)

def calc_ma(prices: list[float], period: int) -> float:
    if len(prices) < period:
        return prices[-1]
    return round(sum(prices[-period:]) / period, 2)

def calc_support_resistance(closes: list[float]) -> dict:
    recent = closes[-48:]
    high = max(recent)
    low = min(recent)
    mid = round((high + low) / 2, 2)
    r1 = round(high - (high - low) * 0.236, 2)
    r2 = round(high - (high - low) * 0.382, 2)
    s1 = round(low + (high - low) * 0.236, 2)
    s2 = round(low + (high - low) * 0.382, 2)
    return {"resistance": [r2, r1, high], "support": [low, s1, s2], "range": round(high - low, 2)}

def analyze_prices(closes: list[float], spot: float | None = None, sentiment_boost: str = "NEUTRAL") -> dict:
    current_price = spot or closes[-1]
    rsi = calc_rsi(closes, 14)
    ma9 = calc_ma(closes, 9)
    ma21 = calc_ma(closes, 21)
    ma50 = calc_ma(closes, 50)
    sr = calc_support_resistance(closes)
    prev_ma9 = calc_ma(closes[:-1], 9)
    prev_ma21 = calc_ma(closes[:-1], 21)

    signals, reason = [], []

    if rsi < 30:
        signals.append("BUY"); reason.append(f"RSI oversold ({rsi})")
    elif rsi > 70:
        signals.append("SELL"); reason.append(f"RSI overbought ({rsi})")

    if prev_ma9 <= prev_ma21 and ma9 > ma21:
        signals.append("BUY"); reason.append("MA9 Golden Cross")
    elif prev_ma9 >= prev_ma21 and ma9 < ma21:
        signals.append("SELL"); reason.append("MA9 Death Cross")

    buy_count = signals.count("BUY")
    sell_count = signals.count("SELL")
    confidence = "MEDIUM"

    if buy_count > sell_count:
        direction = "BUY"
        confidence = "HIGH" if buy_count >= 2 else "MEDIUM"
    elif sell_count > buy_count:
        direction = "SELL"
        confidence = "HIGH" if sell_count >= 2 else "MEDIUM"
    else:
        direction = "NEUTRAL"
        if rsi < 45:
            direction = "SELL"; reason.append(f"RSI bearish ({rsi})"); confidence = "MEDIUM"
        elif rsi > 55:
            direction = "BUY"; reason.append(f"RSI bullish ({rsi})"); confidence = "MEDIUM"
        else:
            reason.append("Market neutral"); confidence = "LOW"

    if sentiment_boost == "BULLISH" and direction == "BUY":
        confidence = "HIGH"; reason.append("📰 News sentiment bullish")
    elif sentiment_boost == "BEARISH" and direction == "SELL":
        confidence = "HIGH"; reason.append("📰 News sentiment bearish")
    elif sentiment_boost == "BULLISH" and direction == "NEUTRAL":
        direction = "BUY"; confidence = "LOW"; reason.append("📰 News suggests BUY")
    elif sentiment_boost == "BEARISH" and direction == "NEUTRAL":
        direction = "SELL"; confidence = "LOW"; reason.append("📰 News suggests SELL")

    entry = current_price
    if direction == "BUY":
        sl = round(entry * 0.98, 2); tp = round(entry * 1.04, 2)
    elif direction == "SELL":
        sl = round(entry * 1.02, 2); tp = round(entry * 0.96, 2)
    else:
        sl = round(entry * 0.99, 2); tp = round(entry * 1.01, 2)

    return {
        "price": current_price, "direction": direction, "entry": entry,
        "sl": sl, "tp": tp, "confidence": confidence,
        "rsi": rsi, "ma9": ma9, "ma21": ma21, "ma50": ma50,
        "support": sr["support"], "resistance": sr["resistance"],
        "range": sr["range"], "reason": "; ".join(reason),
    }

async def analyze() -> dict:
    closes = await fetch_prices()
    if not closes:
        return {"error": "Cannot fetch BTC market data"}
    sentiment = await analyze_news_sentiment()
    boost = sentiment.get("label", "NEUTRAL") if "error" not in sentiment else "NEUTRAL"
    result = analyze_prices(closes, sentiment_boost=boost)
    result["news_sentiment"] = sentiment if "error" not in sentiment else None
    result["news_boost"] = boost
    return result

async def analyze_gold() -> dict:
    closes = await fetch_gold_prices()
    spot = await fetch_gold_spot()
    if not closes:
        return {"error": "Cannot fetch XAUUSD market data", "spot": spot}
    result = analyze_prices(closes, spot)
    result["market"] = "CLOSED (weekend)" if is_market_closed() else "OPEN"
    return result

async def full_analysis() -> dict:
    btc = await analyze()
    gold = await analyze_gold()
    fng = await fetch_fear_greed()
    news = await analyze_news_sentiment()

    combined = {"btc": btc if "error" not in btc else None, "gold": gold if "error" not in gold else None}
    if fng:
        combined["fear_greed"] = fng
    if "error" not in news:
        combined["news_sentiment"] = news
    return combined
