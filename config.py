import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SIGNAL_INTERVAL_MINUTES = int(os.getenv("SIGNAL_INTERVAL_MINUTES", "30"))
SIMULATED = os.getenv("SIMULATED", "true").lower() == "true"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
TV_TICKER = os.getenv("TV_TICKER", "BTCUSDM")
