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

This repository includes a GitHub Action (`.github/workflows/huggingface_sync.yml`) that automatically syncs the `main` branch to a Hugging Face Space.
Make sure to set the `HF_TOKEN` secret in your GitHub repository for the CI/CD pipeline to work correctly.
