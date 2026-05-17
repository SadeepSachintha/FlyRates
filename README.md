---
title: FlyRates
emoji: 💱
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# FlyRates - Telegram Exchange Rate Bot 💱

FlyRates is a high-availability Telegram bot designed for real-time currency exchange rate monitoring. Built with an asynchronous architecture, it efficiently handles on-demand queries, automated subscription updates, and proactive threshold-based notifications.

## Features ✨
- **Premium Web Dashboard:** A stunning, glassmorphic UI displaying real-time LKR exchange rates, automated conversion calculator, database connection status, and user statistics.
- **Real-Time Queries:** Get the latest exchange rates instantly.
- **Subscriptions:** Subscribe to daily or hourly rate updates.
- **Threshold Alerts:** Set custom threshold values and get notified when a currency hits your target rate.
- **Asynchronous Architecture:** High performance and non-blocking I/O using FastAPI and Aiogram.
- **Scheduled Background Tasks:** Powered by APScheduler for reliable background task execution.
- **Database Flexibility:** Uses SQLAlchemy (supports both SQLite and PostgreSQL).

## Bot Commands & Premium UX 🤖📱

FlyRates features a hybrid interface supporting both **instant CLI command typing** (for advanced users) and a **fully-guided visual wizard** (using buttons, emojis, and presets) when commands are typed without arguments.

### Key UX Upgrades:
- **Dynamic Autocomplete Menu:** Whenever you type `/` in the chat, Telegram pops up a visual list of all commands with clear descriptions.
- **Visual Flag Emojis:** Country flags (e.g. `🇺🇸 USD`, `🇪🇺 EUR`, `🇱🇰 LKR`) are built into all menu buttons for effortless scanning.
- **1-Tap Quick Presets:** Tapping a preset button (like `🇺🇸 USD ➡️ 🇱🇰 LKR`) instantly fetches rates or sets up alerts/subscriptions in a single click, completely bypassing selector grids!
- **Settings Control Dashboard:** `/mysubs` opens a visual control panel showing your active configuration with single-tap deletion/addition shortcut buttons.

### Command Reference:
| Command | Type | Description / Usage Example |
| :--- | :--- | :--- |
| `/start` | Basic | Launch the bot, get the welcome menu, and register automatically. |
| `/current` | Rate check | **Interactive:** Click buttons & presets with a `🔄 Refresh` button.<br>**Direct:** `/current USD EUR` |
| `/subscribe` | Recurring | **Interactive:** Button selector for base, target, and daily/hourly updates.<br>**Direct:** `/subscribe USD EUR daily` |
| `/unsubscribe` | Recurring | **Interactive:** Shows active subscriptions; click any `❌` button to delete.<br>**Direct:** `/unsubscribe USD EUR` |
| `/threshold` | Alerts | **Interactive:** Choose currencies, select `<` or `>`, and type target rate when prompted.<br>**Direct:** `/threshold USD LKR < 310.5` |
| `/delthreshold` | Alerts | **Interactive:** Lists your active thresholds; click any `❌` button to delete.<br>**Direct:** `/delthreshold USD LKR` |
| `/mysubs` | Dashboard | Open your visual dashboard to view and manage all active settings. |
| `/help` | Guide | Display a comprehensive guide with interactive examples. |

## Tech Stack 🛠️
- **Web & API Framework:** [FastAPI](https://fastapi.tiangolo.com/)
- **Telegram Bot API:** [Aiogram 3.x](https://aiogram.dev/)
- **Database:** SQLAlchemy, aiosqlite, asyncpg (Supabase PgBouncer optimized)
- **Task Scheduling:** APScheduler
- **Frontend Dashboard:** Premium Glassmorphic Web App (HTML5/Vanilla CSS/Modern JS)
- **Deployment:** Docker, Hugging Face Spaces (24/7 Webhook & Scheduler)

## Environment Setup 🔧

1. **Clone the repository:**
   ```bash
   git clone https://github.com/SadeepSachintha/FlyRates.git
   cd FlyRates
   ```

2. **Create a `.env` file:**
   Populate it with your environment variables based on the required settings (e.g., `BOT_TOKEN`, `WEBHOOK_URL`, `DATABASE_URL`).

3. **Install Dependencies (Local Development):**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Locally:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## Docker Deployment 🐳

You can also run the application using Docker:

```bash
docker build -t flyrates-bot .
docker run -p 8000:8000 --env-file .env flyrates-bot
```

## Hosting on Hugging Face Spaces 🤗

This repository includes a GitHub Actions workflow (`.github/workflows/huggingface_sync.yml`) that automatically syncs the `main` branch to a Hugging Face Space.
Make sure to set the `HF_TOKEN` secret in your GitHub repository for the CI/CD pipeline to work correctly.

### Hugging Face Deployment Optimizations ⚙️

To ensure high-availability and 100% uptime within Hugging Face Spaces, the following environment optimizations are built into the core codebase:

1. **Forced IPv4 Routing (Telegram API & FX Service):**
   - **The Problem:** Hugging Face Spaces defaults to IPv6-first DNS/routing, but `api.telegram.org` is IPv4-only (it lacks `AAAA` records). Because the default fallback fails on the platform's networking stack, connections fail during startup with a `ClientConnectorError` (`Network is unreachable`).
   - **The Solution:** The bot client uses a custom `IPv4AiohttpSession` subclass that injects `family=socket.AF_INET` into the underlying `aiohttp.TCPConnector`. A matching IPv4 constraint is configured on the `ClientSession` inside [services/fx_service.py](file:///d:/xampp/htdocs/FlyRates/services/fx_service.py). This bypasses the platform's IPv6 constraints for 100% successful external API routing.

2. **Supabase Database Pooling:**
   - When deploying with Supabase PostgreSQL, ensure you use the transaction-based connection pooler URL (PgBouncer) on **port 6543**. This prevents connection leakage/exhaustion from concurrent FastAPI server routing and scheduled background intervals.
