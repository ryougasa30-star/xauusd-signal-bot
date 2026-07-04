import asyncio
import uuid
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN
from signal_generator import generate_signal
from market_analyst import analyze, analyze_gold

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

async def send_signal(update: Update, context: ContextTypes.DEFAULT_TYPE, direction: str, entry: float, sl: float, tp: float, confidence: str = "MEDIUM", strategy: str = "Manual", notes: str = None):
    text, sid = build_signal_text(direction, entry, sl, tp, confidence, strategy, notes=notes)
    await update.message.reply_text(text, parse_mode="Markdown")
    logger.info(f"Signal {sid} sent to chat {update.effective_chat.id}")
    return sid

async def send_signal_to_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, direction: str, entry: float, sl: float, tp: float, confidence: str = "MEDIUM", strategy: str = "Manual", notes: str = None):
    text, sid = build_signal_text(direction, entry, sl, tp, confidence, strategy, notes=notes)
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    logger.info(f"Signal {sid} auto-sent to {chat_id}")
    return sid

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Crypto & Gold Signal Bot*\n\n"
        "*BTCUSDM:*\n"
        "/scan - ស្កេន BTC ផ្ទាល់ + Signal\n"
        "/price - តម្លៃ BTC + RSI + MA\n"
        "/autoscan [min] - ស្កេន BTC ដោយស្វ័យប្រវត្តិ\n\n"
        "*XAUUSD:*\n"
        "/xau - តម្លៃមាសផ្ទាល់\n"
        "/scanxau - ស្កេន XAUUSD + Signal\n"
        "/autoscanxau [min] - ស្កេនមាសដោយស្វ័យប្រវត្តិ\n\n"
        "*Manual:*\n"
        "/signal BUY|SELL entry sl tp [confidence]\n"
        "  ឧ: `/signal BUY 65000 64000 67000 HIGH`\n\n"
        "/auto [min] - random signals\n"
        "/stop - បញ្ឈប់ auto ទាំងអស់\n"
        "/ping - test bot",
        parse_mode="Markdown"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong! Bot is online ✅")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ កំពុងទាញតម្លៃ...")
    result = await analyze()
    if "error" in result:
        await msg.edit_text("❗ Cannot fetch price")
        return
    text = (
        "📊 *BTCUSDM Market*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Price: *${result['price']:,.2f}*\n"
        f"RSI(14): *{result['rsi']}*\n"
        f"MA9: *${result['ma9']:,.2f}*\n"
        f"MA21: *${result['ma21']:,.2f}*\n"
        f"MA50: *${result['ma50']:,.2f}*\n"
        f"Signal: *{result['direction']}*\n"
        f"Reason: {result['reason']}"
    )
    await msg.edit_text(text, parse_mode="Markdown")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 កំពុងស្កេនទីផ្សារ BTCUSDM...")
    result = await analyze()
    if "error" in result:
        await msg.edit_text("❗ Cannot scan market: " + result["error"])
        return

    if result["direction"] == "NEUTRAL":
        await msg.edit_text(
            f"📊 *Market Scan Result*\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"Price: *${result['price']:,.2f}*\n"
            f"RSI(14): *{result['rsi']}*\n"
            f"MA9: *${result['ma9']:,.2f}*\n"
            f"MA21: *${result['ma21']:,.2f}*\n"
            f"Signal: *{result['direction']}* 🤷\n"
            f"Reason: {result['reason']}\n\n"
            f"No clear signal right now.",
            parse_mode="Markdown"
        )
        return

    text, sid = build_signal_text(
        result["direction"], result["entry"], result["sl"],
        result["tp"], result["confidence"],
        f"Auto-Scan | {result['reason']}",
        notes=f"RSI: {result['rsi']} | MA9: {result['ma9']} | MA21: {result['ma21']}"
    )
    await msg.edit_text(text, parse_mode="Markdown")

async def xau(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ កំពុងទាញតម្លៃមាស...")
    result = await analyze_gold()
    if "error" in result:
        await msg.edit_text("❗ Cannot fetch XAU price: " + result["error"])
        return
    market = result.get("market", "OPEN")
    closed = "🔴 *MARKET CLOSED* (weekend)" if market == "CLOSED (weekend)" else "🟢 *MARKET OPEN*"
    text = (
        f"🥇 *XAUUSD*\n"
        f"{closed}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Price: *${result['price']:,.2f}*\n"
        f"RSI(14): *{result['rsi']}*\n"
        f"MA9: *${result['ma9']:,.2f}*\n"
        f"MA21: *${result['ma21']:,.2f}*\n"
        f"Signal: *{result['direction']}*\n"
        f"Reason: {result['reason']}"
    )
    await msg.edit_text(text, parse_mode="Markdown")

async def scanxau(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 កំពុងស្កេន XAUUSD...")
    result = await analyze_gold()
    if "error" in result:
        await msg.edit_text("❗ Cannot scan XAU: " + result["error"])
        return

    market = result.get("market", "")
    header_notes = f"Market: {market}" if market else ""
    if result["direction"] == "NEUTRAL":
        text = (
            f"🥇 *XAUUSD Scan*"
            + (f" ({market})" if market else "") + "\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"Price: *${result['price']:,.2f}*\n"
            f"RSI(14): *{result['rsi']}*\n"
            f"MA9: *${result['ma9']:,.2f}*\n"
            f"MA21: *${result['ma21']:,.2f}*\n"
            f"Signal: *{result['direction']}* 🤷\n"
            f"Reason: {result['reason']}"
        )
        await msg.edit_text(text, parse_mode="Markdown")
        return

    text, sid = build_signal_text(
        result["direction"], result["entry"], result["sl"],
        result["tp"], result["confidence"],
        f"Auto-Scan | {result['reason']}",
        notes=f"RSI: {result['rsi']} | MA9: {result['ma9']} | MA21: {result['ma21']} | {header_notes}",
        fmt=SIGNAL_FORMAT_XAU,
    )
    await msg.edit_text(text, parse_mode="Markdown")

async def autoscanxau(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minutes = int(context.args[0]) if context.args else 60
    except ValueError:
        await update.message.reply_text("❗ Usage: /autoscanxau [minutes]")
        return

    stop_all_auto()
    chat_id = update.effective_chat.id

    async def loop():
        while True:
            result = await analyze_gold()
            if "error" not in result and result["direction"] != "NEUTRAL":
                text, sid = build_signal_text(
                    result["direction"], result["entry"], result["sl"],
                    result["tp"], result["confidence"],
                    f"Auto-Scan XAU | {result['reason']}",
                    fmt=SIGNAL_FORMAT_XAU,
                )
                await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                logger.info(f"Auto-scan XAU {sid} sent")
            await asyncio.sleep(minutes * 60)

    _auto_tasks["scanxau"] = asyncio.create_task(loop())
    await update.message.reply_text(f"✅ Auto-scan XAUUSD every {minutes} min started")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 4:
        await update.message.reply_text(
            "❗ Usage: /signal BUY|SELL entry sl tp [confidence] [notes]\n"
            "ឧ: `/signal BUY 65000 64000 67000 HIGH`",
            parse_mode="Markdown"
        )
        return

    direction = context.args[0].upper()
    if direction not in ("BUY", "SELL"):
        await update.message.reply_text("❗ Direction must be BUY or SELL")
        return

    try:
        entry = float(context.args[1])
        sl = float(context.args[2])
        tp = float(context.args[3])
    except ValueError:
        await update.message.reply_text("❗ Price must be numbers")
        return

    confidence = context.args[4].upper() if len(context.args) > 4 else "MEDIUM"
    notes = " ".join(context.args[5:]) if len(context.args) > 5 else None
    await send_signal(update, context, direction, entry, sl, tp, confidence, "Manual", notes)

async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minutes = int(context.args[0]) if context.args else 30
    except ValueError:
        await update.message.reply_text("❗ Usage: /auto [minutes]")
        return

    stop_all_auto()
    chat_id = update.effective_chat.id

    async def loop():
        while True:
            sig = generate_signal()
            await send_signal_to_chat(context, chat_id, sig.direction, sig.entry_price, sig.stop_loss, sig.take_profit, sig.confidence, sig.strategy)
            await asyncio.sleep(minutes * 60)

    _auto_tasks["random"] = asyncio.create_task(loop())
    await update.message.reply_text(f"✅ Random auto-signal every {minutes} min started")

async def autoscan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minutes = int(context.args[0]) if context.args else 60
    except ValueError:
        await update.message.reply_text("❗ Usage: /autoscan [minutes]")
        return

    stop_all_auto()
    chat_id = update.effective_chat.id

    async def loop():
        while True:
            result = await analyze()
            if "error" not in result and result["direction"] != "NEUTRAL":
                await send_signal_to_chat(context, chat_id, result["direction"], result["entry"], result["sl"], result["tp"], result["confidence"], f"Auto-Scan | {result['reason']}")
                logger.info(f"Auto-scan signal sent: {result['direction']} @ {result['entry']}")
            await asyncio.sleep(minutes * 60)

    _auto_tasks["scan"] = asyncio.create_task(loop())
    await update.message.reply_text(f"✅ Auto-scan every {minutes} min started")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stop_all_auto()
    await update.message.reply_text("⏹ All auto tasks stopped")

def stop_all_auto():
    for name, task in _auto_tasks.items():
        if task and not task.done():
            task.cancel()
    _auto_tasks.clear()

_auto_tasks: dict[str, asyncio.Task] = {}

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set in .env")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("xau", xau))
    app.add_handler(CommandHandler("scanxau", scanxau))
    app.add_handler(CommandHandler("autoscanxau", autoscanxau))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("auto", auto))
    app.add_handler(CommandHandler("autoscan", autoscan))
    app.add_handler(CommandHandler("stop", stop))

    logger.info("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
