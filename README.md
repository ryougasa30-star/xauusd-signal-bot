# XAUUSD Signal Bot

FastAPI webapp that receives XAUUSD trading signals from **TradingView webhooks** and pushes them to **Telegram**.

```
TradingView Alert → POST /webhook/tradingview → Parse → Telegram Bot → You
```

## Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   Copy `.env.example` to `.env` and fill in:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   WEBHOOK_SECRET=choose_a_secret_key
   ```

3. **Run**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## TradingView Setup

1. Create an alert in TradingView
2. In the **Alert Message** field (JSON tab), use:
   ```json
   {
     "pair": "XAUUSD",
     "direction": "{{strategy.order.action}}",
     "entry_price": {{strategy.order.price}},
     "stop_loss": {{strategy.order.stop_loss}},
     "take_profit": {{strategy.order.take_profit}},
     "strategy": "My Strategy",
     "confidence": "HIGH"
   }
   ```
3. Set **Webhook URL** to: `https://your-server.com/webhook/tradingview`
4. Add header `x-webhook-secret: your_secret_key` (or use the URL param)

### Supported field names (case-insensitive)

| Field | Accepted aliases |
|-------|-----------------|
| `pair` | `pair`, `symbol`, `ticker`, `market` |
| `direction` | `direction`, `side`, `signal`, `action`, `type` |
| `entry_price` | `entry_price`, `entry`, `price`, `open_price` |
| `stop_loss` | `stop_loss`, `sl`, `stoploss`, `stop` |
| `take_profit` | `take_profit`, `tp`, `takeprofit`, `target` |
| `confidence` | `confidence`, `prob`, `strength` |
| `strategy` | `strategy`, `alert_name`, `name` |
| `notes` | `notes`, `comment`, `message` |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhook/tradingview` | Receive TradingView alert |
| `POST` | `/signal/drop` | Manually drop a signal |
| `GET` | `/signals?limit=20` | Recent signals |
| `GET` | `/` | Status |
| `GET` | `/health` | Health check |
| `POST` | `/config` | Update Telegram config |

## Deploy

Use **ngrok** for testing:
```bash
ngrok http 8000
```
Then set your webhook URL to: `https://xxxx.ngrok-free.app/webhook/tradingview`

Use **Railway / Render / fly.io** for production deployment.

## Get Telegram Credentials

1. Talk to [@BotFather](https://t.me/BotFather) to create a bot → get token
2. Message your bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` → find `chat_id`
