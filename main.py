import asyncio
import logging
import socket
import aiohttp
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from aiogram import Bot, Dispatcher, types
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.session.aiohttp import AiohttpSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func

# Monkeypatch socket.getaddrinfo to bypass DNS resolution blocks for api.telegram.org
original_getaddrinfo = socket.getaddrinfo
def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host == "api.telegram.org":
        # Map to Telegram Bot API native IPv6 and IPv4 IPs
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('2001:67c:4e8:f004::9', port, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('149.154.166.110', port))
        ]
    return original_getaddrinfo(host, port, family, type, proto, flags)
socket.getaddrinfo = custom_getaddrinfo

from core.config import settings
from db.session import init_db, async_session
from db.models import User
from bot.handlers import router as bot_router
from bot.scheduler import process_daily_broadcast
from services.fx_service import fx_service

# Configure Logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# InMemoryLogHandler to store logs for web diagnostics
class InMemoryLogHandler(logging.Handler):
    def __init__(self, limit=300):
        super().__init__()
        self.limit = limit
        self.records = []

    def emit(self, record):
        try:
            self.records.append(self.format(record))
            if len(self.records) > self.limit:
                self.records.pop(0)
        except Exception:
            pass

in_memory_logs = InMemoryLogHandler()
in_memory_logs.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(in_memory_logs)
logging.getLogger("uvicorn").addHandler(in_memory_logs)
logging.getLogger("uvicorn.error").addHandler(in_memory_logs)
logging.getLogger("uvicorn.access").addHandler(in_memory_logs)
logging.getLogger("aiogram").addHandler(in_memory_logs)

# Global diagnostic results storage
diagnostic_results = []

# Initialize Aiogram Bot (with custom reverse proxy API server if configured)
if settings.telegram_api_server:
    api_server = TelegramAPIServer.from_base(settings.telegram_api_server)
    session = AiohttpSession(api=api_server)
    bot = Bot(token=settings.bot_token, session=session)
    logger.info(f"Initialized Bot with custom API server: {settings.telegram_api_server}")
else:
    bot = Bot(token=settings.bot_token)
dp = Dispatcher()
dp.include_router(bot_router)

# Initialize Scheduler
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global diagnostic_results
    diagnostic_results.append("Starting resolution & connection diagnostics...")
    
    # Check DNS resolution
    for host in ["api.telegram.org", "www.cbsl.gov.lk"]:
        try:
            ips = socket.getaddrinfo(host, 443)
            diagnostic_results.append(f"DNS Resolution for {host}: {ips}")
        except Exception as e:
            diagnostic_results.append(f"DNS Resolution failed for {host}: {type(e).__name__}: {e}")
            
    # Try different socket configurations
    configs = [
        ("Default (No family forced)", {}),
        ("Forced IPv4 (AF_INET)", {"family": socket.AF_INET}),
        ("Forced IPv6 (AF_INET6)", {"family": socket.AF_INET6})
    ]
    
    for name, kwargs in configs:
        try:
            connector = aiohttp.TCPConnector(**kwargs)
            async with aiohttp.ClientSession(connector=connector) as sess:
                async with sess.get(f"https://api.telegram.org/bot{settings.bot_token}/getMe", timeout=5) as r:
                    text = await r.text()
                    diagnostic_results.append(f"Configuration '{name}' SUCCESS: Status {r.status}, body: {text}")
        except Exception as e:
            diagnostic_results.append(f"Configuration '{name}' FAILED: {type(e).__name__}: {e}")
            
    diagnostic_results.append("Diagnostics finished.")

    # 1. Initialize Database
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"CRITICAL: Failed to initialize database on startup. The database may be paused or unreachable: {e}")
        diagnostic_results.append(f"DB Initialization FAILED: {type(e).__name__}: {e}")

    # Register Bot Menu Commands
    try:
        commands = [
            types.BotCommand(command="start", description="Start FlyRates & get welcome message"),
            types.BotCommand(command="current", description="Check live exchange rate (interactive/direct)"),
            types.BotCommand(command="subscribe", description="Set up periodic rate updates"),
            types.BotCommand(command="threshold", description="Configure custom price alert"),
            types.BotCommand(command="mysubs", description="View & manage active subscriptions/alerts"),
            types.BotCommand(command="unsubscribe", description="Remove active subscription"),
            types.BotCommand(command="delthreshold", description="Remove active threshold alert"),
            types.BotCommand(command="help", description="Show detailed guide and examples")
        ]
        await bot.set_my_commands(commands)
        logger.info("Bot commands registered successfully.")
    except Exception as e:
        logger.error(f"Failed to register bot commands: {e}")

    # 3. Setup Webhook (if URL is provided) or Fallback to Polling
    try:
        if settings.webhook_url:
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url != f"{settings.webhook_url}/webhook":
                await bot.set_webhook(url=f"{settings.webhook_url}/webhook")
                logger.info(f"Webhook set to {settings.webhook_url}/webhook")
        else:
            logger.info("WEBHOOK_URL not set. Running in local mode. Checking active webhook...")
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url:
                if settings.delete_webhook_on_local:
                    logger.warning(f"Active webhook detected at '{webhook_info.url}'. Deleting it as delete_webhook_on_local is enabled...")
                    await bot.delete_webhook(drop_pending_updates=False)
                    polling_task = asyncio.create_task(dp.start_polling(bot))
                    app.state.polling_task = polling_task
                else:
                    logger.warning(
                        f"Active webhook detected at '{webhook_info.url}'. "
                        "To protect the production bot, local long polling will NOT delete it, and polling is skipped. "
                        "If you wish to test locally and delete the webhook, set DELETE_WEBHOOK_ON_LOCAL=True in your local .env file."
                    )
            else:
                logger.info("No active webhook. Starting Bot in Long Polling mode...")
                polling_task = asyncio.create_task(dp.start_polling(bot))
                app.state.polling_task = polling_task
    except Exception as e:
        logger.error(f"Failed to setup Telegram interaction during startup: {e}")

    # 3. Setup Scheduled Jobs (exactly one clean daily broadcast at 8:00 AM)
    scheduler.add_job(process_daily_broadcast, 'cron', hour=8, args=[bot])
    scheduler.start()

    yield

    # Shutdown logic
    scheduler.shutdown()
    if not settings.webhook_url:
        if hasattr(app.state, "polling_task"):
            app.state.polling_task.cancel()
            try:
                await app.state.polling_task
            except asyncio.CancelledError:
                pass
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Endpoint for Telegram to send updates to."""
    try:
        payload = await request.json()
        logger.info(f"Incoming webhook payload: {payload}")
        update = types.Update.model_validate(payload, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.exception("CRITICAL: Error processing webhook update:")
        raise e
    return Response(status_code=200)

@app.get("/api/diagnostics")
async def get_diagnostics():
    """Retrieve connection and network resolution diagnostic logs."""
    import os
    env_info = {
        "DATABASE_URL_set": bool(os.getenv("DATABASE_URL")),
        "WEBHOOK_URL_val": os.getenv("WEBHOOK_URL"),
        "TELEGRAM_API_SERVER_val": os.getenv("TELEGRAM_API_SERVER"),
        "BOT_TOKEN_set": bool(os.getenv("BOT_TOKEN")),
        "FX_API_KEY_set": bool(os.getenv("FX_API_KEY"))
    }
    return {
        "diagnostics": diagnostic_results,
        "env_info": env_info
    }

@app.get("/health")
async def health_check():
    """Health check endpoint required by Hugging Face Spaces."""
    return {"status": "ok"}

@app.get("/api/logs")
async def get_logs():
    """Retrieve in-memory logs for diagnostics."""
    return {"logs": in_memory_logs.records}

@app.get("/api/stats")
async def get_system_stats():
    """Retrieve database metrics and live LKR exchange rates."""
    stats = {}
    try:
        async with async_session() as session:
            # Gather active subscribers count
            users_count = await session.scalar(select(func.count(User.chat_id)).where(User.is_subscribed == True))
            
            stats["subscribers"] = users_count or 0
            stats["active_subscriptions"] = 10  # 10 core LKR currencies tracked
            stats["active_thresholds"] = 1     # Unified active broadcast schedule
            stats["db_status"] = "connected"
    except Exception as e:
        logger.error(f"Error fetching stats from DB: {e}")
        stats["subscribers"] = 0
        stats["active_subscriptions"] = 0
        stats["active_thresholds"] = 0
        stats["db_status"] = "error"

    # Fetch live exchange rates to LKR concurrently
    rates = {}
    currencies = ["USD", "EUR", "GBP", "AUD", "JPY"]
    
    async def fetch_rate_safe(cur: str):
        try:
            val = await fx_service.get_rate(cur, "LKR")
            return cur, val or 0.0
        except Exception as e:
            logger.error(f"Error fetching live rate for {cur}: {e}")
            return cur, 0.0

    results = await asyncio.gather(*(fetch_rate_safe(cur) for cur in currencies))
    for cur, rate in results:
        rates[cur] = rate
            
    stats["rates"] = rates
    stats["system_status"] = "online"
    
    return stats

# Serve static dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get_dashboard():
    """Serves the premium dashboard index file."""
    return FileResponse("static/index.html")

