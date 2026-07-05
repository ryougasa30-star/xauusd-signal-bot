import asyncio
import uuid
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN
from signal_generator import generate_signal
from market_analyst import analyze, analyze_gold, analyze_news_sentiment, fetch_fear_greed, full_analysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SIGNAL_FORMAT_BTC = (
    "{emoji} *BTCUSDM SIGNAL*\n"
    "━━━━━━━━━━━━━━━━\n"
    "Direction: *{direction}*\n"
    "Entry: *${entry}*\n"
    "Stop Loss: *${sl}*\n"
    "Take Profit: *${tp}*\n"
    "Confidence: *{confidence}*\n"
    "Strategy: {strategy}\n"
    "Signal ID: `{id}`\n"
    "━━━━━━━━━━━━━━━━\n"
    "🕐 {time}"
)

SIGNAL_FORMAT_XAU = (
    "{emoji} *XAUUSD SIGNAL*\n"
    "━━━━━━━━━━━━━━━━\n"
    "Direction: *{direction}*\n"
    "Entry: *${entry}*\n"
    "Stop Loss: *${sl}*\n"
    "Take Profit: *${tp}*\n"
    "Confidence: *{confidence}*\n"
    "Strategy: {strategy}\n"
    "Signal ID: `{id}`\n"
    "━━━━━━━━━━━━━━━━\n"
    "🕐 {time}"
)

def build_signal_text(direction, entry, sl, tp, confidence="MEDIUM", strategy="Manual", signal_id=None, notes=None, fmt=SIGNAL_FORMAT_BTC):
    emoji = "🟢" if direction.upper() == "BUY" else "🔴"
    sid = signal_id or uuid.uuid4().hex[:8].upper()
    text = fmt.format(
        emoji=emoji, direction=direction.upper(),
        entry=entry, sl=sl, tp=tp,
        confidence=confidence.upper(),
        strategy=strategy, id=sid,
        time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
    if notes:
        text += f"\n📝 {notes}"
    return text, sid

async def send_signal(update, ctx, direction, entry, sl, tp, confidence="MEDIUM", strategy="Manual", notes=None):
    text, sid = build_signal_text(direction, entry, sl, tp, confidence, strategy, notes=notes)
    await update.message.reply_text(text, parse_mode="Markdown")
    return sid

async def send_signal_to_chat(ctx, chat_id, direction, entry, sl, tp, confidence="MEDIUM", strategy="Manual", notes=None):
    text, sid = build_signal_text(direction, entry, sl, tp, confidence, strategy, notes=notes)
    await ctx.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    return sid

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Crypto & Gold Signal Bot v3*\n\n"
        "*Market:*\n"
        "/scan - ស្កេន BTC + Signal\n"
        "/scanxau - ស្កេន XAUUSD + Signal\n"
        "/price - BTC price + RSI + MA\n"
        "/xau - XAUUSD price\n\n"
        "*News & Sentiment:*\n"
        "/news - ព័ត៌មាន Crypto ចុងក្រោយ\n"
        "/fear - Crypto Fear & Greed Index\n"
        "/analysis - វិភាគទីផ្សារពេញលេញ\n\n"
        "*Auto:*\n"
        "/autoscan [min] - ស្កេន BTC ដោយស្វ័យប្រវត្តិ\n"
        "/autoscanxau [min] - ស្កេនមាសដោយស្វ័យប្រវត្តិ\n\n"
        "*Manual:*\n"
        "/signal BUY|SELL entry sl tp [confidence]\n"
        "  ឧ: `/signal BUY 65000 64000 67000 HIGH`\n\n"
        "/stop - បញ្ឈប់ auto\n"
        "/ping - test",
        parse_mode="Markdown"
    )

async def ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong! Bot is online ✅ v3")

async def price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ កំពុងទាញតម្លៃ...")
    result = await analyze()
    if "error" in result:
        await msg.edit_text("❗ " + result["error"]); return
    sr = f"S: ${result['support'][0]:,.0f}-${result['support'][1]:,.0f} | R: ${result['resistance'][1]:,.0f}-${result['resistance'][2]:,.0f}"
    await msg.edit_text(
        "📊 *BTCUSDM Market*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Price: *${result['price']:,.2f}*\n"
        f"RSI(14): *{result['rsi']}*\n"
        f"MA9: *${result['ma9']:,.2f}* | MA21: *${result['ma21']:,.2f}*\n"
        f"Range: *${result['range']:,.0f}*\n"
        f"{sr}\n"
        f"Signal: *{result['direction']}* ({result['confidence']})\n"
        f"📰 {result.get('news_boost', '—')}\n"
        f"Reason: {result['reason']}",
        parse_mode="Markdown"
    )

async def scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 កំពុងស្កេន BTCUSDM...")
    result = await analyze()
    if "error" in result:
        await msg.edit_text("❗ " + result["error"]); return
    if result["direction"] == "NEUTRAL":
        await msg.edit_text(
            f"📊 *Market Scan*\n━━━━━━━━━━━━━━━━\n"
            f"Price: *${result['price']:,.2f}*\nRSI: *{result['rsi']}*\n"
            f"Signal: *NEUTRAL* 🤷\n{result['reason']}", parse_mode="Markdown")
        return
    notes = f"RSI: {result['rsi']} | 📰 {result.get('news_boost','—')}"
    text, sid = build_signal_text(
        result["direction"], result["entry"], result["sl"], result["tp"],
        result["confidence"], f"Scan | {result['reason']}", notes=notes)
    await msg.edit_text(text, parse_mode="Markdown")

async def xau(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ កំពុងទាញតម្លៃមាស...")
    result = await analyze_gold()
    if "error" in result:
        await msg.edit_text("❗ " + result["error"]); return
    closed = "🔴 *CLOSED*" if result.get("market") == "CLOSED (weekend)" else "🟢 *OPEN*"
    await msg.edit_text(
        f"🥇 *XAUUSD* ({closed})\n━━━━━━━━━━━━━━━━\n"
        f"Price: *${result['price']:,.2f}*\nRSI: *{result['rsi']}*\n"
        f"MA9: *${result['ma9']:,.2f}* | MA21: *${result['ma21']:,.2f}*\n"
        f"Signal: *{result['direction']}*\n{result['reason']}", parse_mode="Markdown")

async def scanxau(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 កំពុងស្កេន XAUUSD...")
    result = await analyze_gold()
    if "error" in result:
        await msg.edit_text("❗ " + result["error"]); return
    if result["direction"] == "NEUTRAL":
        await msg.edit_text(
            f"🥇 *XAUUSD* ({result.get('market','')})\n━━━━━━━━━━━━━━━━\n"
            f"Price: *${result['price']:,.2f}*\nRSI: *{result['rsi']}*\n"
            f"Signal: *NEUTRAL* 🤷\n{result['reason']}", parse_mode="Markdown"); return
    text, sid = build_signal_text(
        result["direction"], result["entry"], result["sl"], result["tp"],
        result["confidence"], f"Scan XAU | {result['reason']}",
        notes=f"RSI: {result['rsi']} | {result.get('market','')}", fmt=SIGNAL_FORMAT_XAU)
    await msg.edit_text(text, parse_mode="Markdown")

async def news(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ កំពុងទាញព័ត៌មាន...")
    sentiment = await analyze_news_sentiment()
    if "error" in sentiment:
        await msg.edit_text("❗ Cannot fetch news"); return
    emoji = "🟢" if sentiment["label"] == "BULLISH" else "🔴" if sentiment["label"] == "BEARISH" else "⚪"
    text = f"📰 *Crypto News* | Sentiment: {emoji} *{sentiment['label']}* ({sentiment['score']})\n━━━━━━━━━━━━━━━━\n"
    for a in sentiment["articles"][:5]:
        text += f"• [{a['source']}] {a['title'][:80]}...\n"
    text += f"\n/analysis - វិភាគពេញលេញ"
    await msg.edit_text(text, parse_mode="Markdown")

async def fear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ កំពុងទាញ Fear & Greed...")
    fng = await fetch_fear_greed()
    if not fng:
        await msg.edit_text("❗ Cannot fetch Fear & Greed"); return
    v = fng["value"]
    if v <= 25: emoji = "😱"
    elif v <= 45: emoji = "😟"
    elif v <= 55: emoji = "😐"
    elif v <= 75: emoji = "😊"
    else: emoji = "🚀"
    bar = "█" * (v // 5) + "░" * (20 - v // 5)
    await msg.edit_text(
        f"📊 *Crypto Fear & Greed Index*\n━━━━━━━━━━━━━━━━\n"
        f"{emoji} *{fng['classification']}*\n"
        f"Value: *{v}/100*\n"
        f"`{bar}`\n\n"
        f"0-25: Extreme Fear 😱\n"
        f"26-45: Fear 😟\n"
        f"46-55: Neutral 😐\n"
        f"56-75: Greed 😊\n"
        f"76-100: Extreme Greed 🚀",
        parse_mode="Markdown"
    )

async def analysis(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ កំពុងវិភាគទីផ្សារ...")
    result = await full_analysis()
    text = "📊 *Market Analysis*\n━━━━━━━━━━━━━━━━\n"

    if result.get("btc"):
        b = result["btc"]
        text += f"*BTCUSDM:* ${b['price']:,.0f} | RSI: {b['rsi']} | *{b['direction']}* ({b['confidence']})\n"
        text += f"  📰 News: {b.get('news_boost','—')}\n"

    if result.get("gold"):
        g = result["gold"]
        m = "🔴CLOSED" if g.get("market") == "CLOSED (weekend)" else "🟢OPEN"
        text += f"*XAUUSD:* ${g['price']:,.0f} | RSI: {g['rsi']} | *{g['direction']}* ({m})\n"

    if result.get("fear_greed"):
        f = result["fear_greed"]
        text += f"*F&G:* {f['value']}/100 ({f['classification']})\n"

    if result.get("news_sentiment"):
        n = result["news_sentiment"]
        e = "🟢" if n["label"] == "BULLISH" else "🔴" if n["label"] == "BEARISH" else "⚪"
        text += f"*News:* {e} {n['label']} ({n['score']}) {n['count']} articles\n"

    text += "━━━━━━━━━━━━━━━━\n/scan - drop signal"
    await msg.edit_text(text, parse_mode="Markdown")

async def signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 4:
        await update.message.reply_text("❗ /signal BUY|SELL entry sl tp [confidence]\nឧ: `/signal BUY 65000 64000 67000 HIGH`", parse_mode="Markdown"); return
    d = ctx.args[0].upper()
    if d not in ("BUY", "SELL"): await update.message.reply_text("❗ BUY or SELL"); return
    try:
        entry, sl, tp = float(ctx.args[1]), float(ctx.args[2]), float(ctx.args[3])
    except: await update.message.reply_text("❗ Price must be numbers"); return
    conf = ctx.args[4].upper() if len(ctx.args) > 4 else "MEDIUM"
    notes = " ".join(ctx.args[5:]) if len(ctx.args) > 5 else None
    await send_signal(update, ctx, d, entry, sl, tp, conf, "Manual", notes)

async def auto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try: minutes = int(ctx.args[0]) if ctx.args else 30
    except: await update.message.reply_text("❗ /auto [minutes]"); return
    stop_all_auto(); cid = update.effective_chat.id
    async def loop():
        while True:
            s = generate_signal()
            await send_signal_to_chat(ctx, cid, s.direction, s.entry_price, s.stop_loss, s.take_profit, s.confidence, s.strategy)
            await asyncio.sleep(minutes * 60)
    _auto_tasks["random"] = asyncio.create_task(loop())
    await update.message.reply_text(f"✅ Random signal every {minutes} min")

async def autoscan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try: minutes = int(ctx.args[0]) if ctx.args else 60
    except: await update.message.reply_text("❗ /autoscan [minutes]"); return
    stop_all_auto(); cid = update.effective_chat.id
    async def loop():
        while True:
            result = await analyze()
            if "error" not in result and result["direction"] != "NEUTRAL":
                await send_signal_to_chat(ctx, cid, result["direction"], result["entry"], result["sl"], result["tp"], result["confidence"], f"Scan | {result['reason']}")
            await asyncio.sleep(minutes * 60)
    _auto_tasks["scan"] = asyncio.create_task(loop())
    await update.message.reply_text(f"✅ Auto-scan BTC every {minutes} min")

async def autoscanxau(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try: minutes = int(ctx.args[0]) if ctx.args else 60
    except: await update.message.reply_text("❗ /autoscanxau [minutes]"); return
    stop_all_auto(); cid = update.effective_chat.id
    async def loop():
        while True:
            result = await analyze_gold()
            if "error" not in result and result["direction"] != "NEUTRAL":
                text, sid = build_signal_text(result["direction"], result["entry"], result["sl"], result["tp"], result["confidence"], f"Scan XAU | {result['reason']}", fmt=SIGNAL_FORMAT_XAU)
                await ctx.bot.send_message(chat_id=cid, text=text, parse_mode="Markdown")
            await asyncio.sleep(minutes * 60)
    _auto_tasks["scanxau"] = asyncio.create_task(loop())
    await update.message.reply_text(f"✅ Auto-scan XAU every {minutes} min")

async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    stop_all_auto(); await update.message.reply_text("⏹ All auto stopped")

def stop_all_auto():
    for name, task in _auto_tasks.items():
        if task and not task.done(): task.cancel()
    _auto_tasks.clear()

_auto_tasks: dict[str, asyncio.Task] = {}

def main():
    if not TELEGRAM_BOT_TOKEN: return
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    for cmd, handler in [
        ("start", start), ("ping", ping), ("price", price),
        ("scan", scan), ("xau", xau), ("scanxau", scanxau),
        ("news", news), ("fear", fear), ("analysis", analysis),
        ("signal", signal), ("auto", auto),
        ("autoscan", autoscan), ("autoscanxau", autoscanxau),
        ("stop", stop),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
    logger.info("Bot v3 started...")
    app.run_polling()

if __name__ == "__main__":
    main()
