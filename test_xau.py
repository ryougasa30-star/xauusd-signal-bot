import asyncio, httpx
from market_analyst import analyze_gold

async def main():
    r = await analyze_gold()
    if "error" in r:
        text = "❌ " + r["error"]
    else:
        market = r.get("market", "")
        closed = "🔴 MARKET CLOSED (weekend)" if "CLOSED" in market else "🟢 MARKET OPEN"
        text = (
            f"🥇 *XAUUSD*\n"
            f"{closed}\n\n"
            f"Price: *${r['price']:,.2f}*\n"
            f"RSI(14): *{r['rsi']}*\n"
            f"MA9: *${r['ma9']:,.2f}*\n"
            f"MA21: *${r['ma21']:,.2f}*\n"
            f"Signal: *{r['direction']}*\n"
            f"Confidence: *{r['confidence']}*\n"
            f"Entry: *${r['entry']:,.2f}*\n"
            f"SL: *${r['sl']:,.2f}* | TP: *${r['tp']:,.2f}*\n\n"
            f"Reason: {r['reason']}"
        )
    httpx.post(
        "https://api.telegram.org/bot8639043211:AAFX8V_94OqrDy5-hFlYWVWhUVCT43RW9fY/sendMessage",
        json={"chat_id": 6651779200, "text": text, "parse_mode": "Markdown"},
    )
    print("Sent XAUUSD result to Telegram!")

asyncio.run(main())
