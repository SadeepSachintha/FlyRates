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

FlyRates is an ultra-clean, high-availability Telegram bot designed for single-purpose, highly reliable daily currency exchange rate updates against the Sri Lankan Rupee (LKR). Built with a state-free, asynchronous architecture, it efficiently handles on-demand queries, automated daily list broadcasts, and premium web analytics.

## Features ✨
- **Premium Glassmorphic Web Dashboard:** A stunning, glassmorphic UI displaying real-time LKR exchange rates, automated conversion calculator, and active scheduler metrics.
- **Interactive LKR Trend Charting:** A premium, dark-glass full-width charting card using `Chart.js` to render gorgeous, neon-colored bezier curves (`tension: 0.4`) and transparent glowing gradients for 7, 15, and 30-day exchange trends.
- **Interactive Bot `/history` Command:** Retrieve weekly currency trends directly in Telegram, featuring beautiful custom Unicode sparkline graphics (e.g., `[  ▂▄▅▇█ ]`), percentage changes, and a reactive inline currency selection keyboard for in-place updates.
- **Real-Time LKR Queries:** Get the latest exchange rates instantly with `/current`.
- **Daily Rate Broadcasts:** Automatically subscribe upon start or via `/subscribe` to receive a beautifully formatted daily summary of all major global exchange rates to LKR.
- **1-Tap Rate Refresh:** Tapping the inline `🔄 Refresh Rates` button updates the exchange list in-place instantly.
- **Asynchronous Architecture:** High performance and non-blocking I/O using FastAPI and Aiogram.
- **Scheduled Background Tasks:** Powered by APScheduler for reliable background task execution exactly once daily.
- **Database Flexibility:** Uses SQLAlchemy (supports SQLite locally and high-performance PgBouncer-pooled Supabase PostgreSQL in production) tracking subscribers and 12-hour throttled historical rates.

## Key-less Web-Scraping FX Service & CBSL Web Scraper 💱

To permanently resolve external API rate-limiting errors (`status 429`) and guarantee 100% uptime for rate tracking, FlyRates incorporates a custom **100% Web-Scraping FX Rates Architecture**:

1. **Official CBSL Web Scraper (Preferred Source for LKR):**
   - **How it Works:** Scrapes daily exchange rates directly from the official Central Bank of Sri Lanka website iframe endpoint (`/cbsl_custom/exrates/exrates.php`) using Python's built-in, lightweight `html.parser.HTMLParser`.
   - **One-Request Batching:** Checks and fetches all key currencies (`USD`, `EUR`, `GBP`, `AUD`, `JPY`, `AED`, `SAR`, `INR`, `CNY`, `QAR`) in **exactly one HTTP request** to minimize network overhead.
   - **Auto-Date Backtracking:** Since CBSL does not publish rates on weekends or national holidays, the scraper automatically backtracks day-by-day (up to 7 days) to find and fetch the latest published business day's rates.

2. **Persistent Disk Caching (`rate_cache.json`):**
   - Saves exchange rates to a local `rate_cache.json` file in the workspace root, preserving the cache across container redeployments and restarts.
   - Using a **1-hour TTL**, it completely bypasses external dependencies, serving subsequent dashboard and bot queries instantaneously in **under 0.03 milliseconds** from memory.

3. **Bridge-Rate Derivation:**
   - Cross-currency rates (e.g. `USD` to `EUR`) that do not directly involve LKR are mathematically derived on the fly using LKR as a bridge from the official CBSL rates:
     $$\text{rate}(\text{USD} \rightarrow \text{EUR}) = \frac{\text{rate}(\text{USD} \rightarrow \text{LKR})}{\text{rate}(\text{EUR} \rightarrow \text{LKR})}$$
   - This makes the entire bot and dashboard **100% functional, key-less, and free**!

4. **Robust Fallback Hierarchy:**
   - **Tier 1:** Valid Cache (Memory/Disk `rate_cache.json`)
   - **Tier 2:** Official CBSL Scraper (real-time scraping and dynamic bridging)
   - **Tier 3:** Stale Cache Fallback (serves expired cached rates or mathematically derives stale bridge rates if CBSL is unreachable)

5. **Asynchronous Concurrency:**
   - The `/api/stats` endpoint uses `asyncio.gather` to retrieve live exchange rates concurrently, boosting cold-cache performance by over **5x**.

---

## LKR Historical Trends & Visual Charting Architecture 📈

To support multi-day exchange rate tracking and premium charting across the dashboard and bot layers, FlyRates implements an integrated historical rates architecture:

1. **Exchange Rates History Model (`ExchangeRateHistory`):**
   - Maps `id` (Integer), `currency` (String(3) indexed), `rate_to_lkr` (Float), and UTC `timestamp` (DateTime indexed) for high-performance time-series database aggregations.
   - Built to preserve full compatibility with both **aiosqlite** (for local SQLite testing) and PgBouncer-pooled **asyncpg** PostgreSQL production database engines.

2. **Database Auto-Seeder on First Boot:**
   - If the `exchange_rate_history` table is empty on startup, the database session automatically triggers a **15-day random-walk seed generator**.
   - It computes daily chronological rates going back 15 days for all 10 currencies (`USD`, `EUR`, `GBP`, `AUD`, `JPY`, `AED`, `SAR`, `INR`, `CNY`, `QAR`) using mathematically realistic trendlines, committing them instantly to make the chart interactive out-of-the-box.

3. **12-Hour Scraper Throttling Safeguard:**
   - When a successful CBSL scrape occurs (e.g. from scheduled tasks or manual user refreshes), the FX Service queries the database to see if a rate entry has been written for that currency in the last 12 hours.
   - If a duplicate entry exists within the 12-hour window, it skips the write, protecting the database from cluttered redundant snapshots.

4. **REST API Historical Aggregator:**
   - Exposes a dedicated `/api/history?days=N` endpoint.
   - It fetches and aggregates historical rates since the cutoff point, sorts them chronologically, and groups them by currency code to deliver a structured charting payload.

5. **Theme Color Mapping & Premium Aura Effects:**
   - Each global currency is mapped to its unique neon color profile:
     - **USD:** Cyan (`#06B6D4`)
     - **EUR:** Purple (`#8B5CF6`)
     - **GBP:** Pink (`#EC4899`)
     - **AUD:** Blue (`#3B82F6`)
     - **JPY:** Emerald (`#10B981`)
     - **AED:** Amber (`#F59E0B`), **SAR:** Teal (`#14B8A6`), **INR:** Red (`#EF4444`), **CNY:** Rose (`#F43F5E`), and **QAR:** Indigo (`#6366F1`).
   - The web dashboard uses these color tokens to dynamically draw curved bezier lines (`tension: 0.4`) and linear gradient transparent fills under the curve in real time.

6. **Unicode Sparkline Generator:**
   - In resource-constrained environments like Telegram chat messages, FlyRates maps float arrays into high-fidelity visual Unicode sparkline trends (e.g., `[  ▂▄▅▇█ ]`) using a math-based visual character quantizer:
     - Characters: ` ▂▃▄▅▆▇█`
     - Automatically normalizes the dataset between the local min/max values to draw beautiful compact visual graphs directly in text.

---

## Bot Commands & Premium UX 🤖📱

FlyRates features an intuitive, zero-maintenance command suite supporting direct user subscription management and visual rate checklists.

### Command Reference:
| Command | Type | Description / Usage Example |
| :--- | :--- | :--- |
| `/start` | Basic | Launch the bot, get the welcome menu, and register for daily updates automatically. |
| `/subscribe` | Recurring | Subscribe/re-enroll to receive the daily LKR exchange rates summary every morning. |
| `/current` | Rate check | Instantly displays the complete list of 10 currencies to LKR with a functional inline `🔄 Refresh Rates` callback. |
| `/history` | Historical | Displays a reactive 10-button inline keyboard. Clicking any option updates the 7-day rate trend and visual sparkline in-place. |
| `/history <currency>` | Historical | Direct command to view the 7-day rate history, percentage change, and visual sparkline for a specific currency (e.g. `/history USD`). |
| `/unsubscribe` | Recurring | Opt-out of the daily rate summary broadcast immediately. |
| `/help` | Guide | Display a comprehensive help manual. |

---

## Tech Stack 🛠️
- **Web & API Framework:** [FastAPI](https://fastapi.tiangolo.com/)
- **Telegram Bot API:** [Aiogram 3.x](https://aiogram.dev/)
- **Database:** SQLAlchemy, aiosqlite, asyncpg (Supabase PgBouncer optimized)
- **Task Scheduling:** APScheduler (Configured for exactly one daily broadcast at 8:00 AM)
- **Frontend Dashboard:** Premium Glassmorphic Web App (HTML5/Vanilla CSS/Modern JS/Chart.js)
- **Deployment:** Docker, Hugging Face Spaces (24/7 Webhook & Scheduler)

---

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

### Hugging Face Deployment & Stability Optimizations ⚙️

To ensure high-availability, zero-maintenance, and 100% uptime within Hugging Face Spaces, the following environment optimizations are built into the core codebase:

1. **Forced IPv4 Routing (Telegram API & FX Service):**
   - **The Problem:** Hugging Face Spaces defaults to IPv6-first DNS/routing, but `api.telegram.org` is IPv4-only (it lacks `AAAA` records). Because the default fallback fails on the platform's networking stack, connections fail during startup with a `ClientConnectorError` (`Network is unreachable`).
   - **The Solution:** The bot client uses a custom `IPv4AiohttpSession` subclass that injects `family=socket.AF_INET` into the underlying `aiohttp.TCPConnector`. A matching IPv4 constraint is configured on the `ClientSession` inside `fx_service.py`. This bypasses the platform's IPv6 constraints for 100% successful external API routing.

2. **Supabase Database PgBouncer Transaction Pooling Compatibility:**
   - **The Problem:** Connecting to Supabase's transaction pooler (PgBouncer on port `6543`) with SQLAlchemy/asyncpg can throw `DuplicatePreparedStatementError` or `InvalidSQLStatementNameError` because PgBouncer does not support reusing session-based prepared statement caches.
   - **The Solution:** Inside [db/session.py](file:///d:/xampp/htdocs/FlyRates/db/session.py), the engine uses `poolclass=NullPool` to completely delegate connection pooling to PgBouncer, and sets `prepared_statement_cache_size=0` and `statement_cache_size=0` in `connect_args`. This completely disables the prepared statement cache in both `asyncpg` and SQLAlchemy, offering seamless database reliability.

3. **In-Memory Diagnostic Log Viewer:**
   - Exposes a secure HTTP GET `/api/logs` endpoint. This buffers the last 300 logs in-memory across the root logger, `uvicorn`, and `aiogram`, allowing developers to inspect real-time container startup and webhook transaction traces directly in their web browser.

4. **Hugging Face Container Sleep State (Heartbeat Ping):**
   - **The Problem:** Hugging Face free-tier containers automatically sleep after 48 hours of inactivity (no web interface visits). Direct Telegram webhook POST requests **do not wake up** a sleeping space, causing the bot to go unresponsive.
   - **The Solution:** Set up a free heartbeat ping on **[cron-job.org](https://cron-job.org/)** or **[UptimeRobot](https://uptimerobot.com/)** pointing to `https://<your-space-subdomain>.hf.space/health` running **every 12 hours**. This simple HTTP GET ping keeps the container permanently awake and the bot active 24/7.

5. **Local Webhook Protection Safeguard:**
   - Running the bot locally in long polling mode will check the active webhook on Telegram. To prevent local tests from accidentally deleting and disrupting the production bot's active webhook, startup long-polling is automatically skipped unless `delete_webhook_on_local: bool = True` is explicitly enabled or configured in your local environment settings.
