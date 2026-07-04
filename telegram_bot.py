import logging
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from models import Signal

logger = logging.getLogger(__name__)

_forward_url = None
_chat_id = None

def configure(token: str | None = None, chat_id: str | None = None):
    global _forward_url, _chat_id
    t = token or TELEGRAM_BOT_TOKEN
    c = chat_id or TELEGRAM_CHAT_ID
    _chat_id = c
    if t and c:
        _forward_url = f"https://api.telegram.org/bot{t}/sendMessage"
    else:
        _forward_url = None

async def send_signal(signal: Signal) -> bool:
    if not _forward_url or not _chat_id:
        logger.warning("Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
        return False

    emoji = "🟢" if signal.direction == "BUY" else "🔴"
    message = (
        f"{emoji} *BTCUSDM SIGNAL*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Direction: *{signal.direction}*\n"
        f"Entry: *${signal.entry_price}*\n"
        f"Stop Loss: *${signal.stop_loss}*\n"
        f"Take Profit: *${signal.take_profit}*\n"
        f"Confidence: *{signal.confidence}*\n"
        f"Strategy: {signal.strategy}\n"
        f"Signal ID: `{signal.id}`\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🕐 {signal.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"
    )

    if signal.notes:
        message += f"\n📝 {signal.notes}"

    import httpx
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(_forward_url, json={
                "chat_id": _chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }, timeout=10)
            resp.raise_for_status()
            logger.info(f"Signal {signal.id} sent to Telegram")
            return True
        except Exception as e:
            logger.error(f"Failed to send to Telegram: {e}")
            return False
