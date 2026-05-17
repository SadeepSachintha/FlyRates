import logging
import socket
import aiohttp
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from aiogram import Bot, Dispatcher, types
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
from db.models import User, Subscription, Threshold
from bot.handlers import router as bot_router
from bot.scheduler import process_subscriptions, process_thresholds
from services.fx_service import fx_service

# Configure Logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# Global diagnostic results storage
diagnostic_results = []

# Initialize Aiogram Bot using standard session to leverage Hugging Face's NAT64 routing
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
    for host in ["api.telegram.org", "v6.exchangerate-api.com"]:
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
                async with sess.get("https://api.telegram.org/bot8962490919:AAFtXUpwmYe8SrtkLjvsDFTntz2El9ckPs0/getMe", timeout=5) as r:
                    text = await r.text()
                    diagnostic_results.append(f"Configuration '{name}' SUCCESS: Status {r.status}, body: {text}")
        except Exception as e:
            diagnostic_results.append(f"Configuration '{name}' FAILED: {type(e).__name__}: {e}")
            
    diagnostic_results.append("Diagnostics finished.")

    # 1. Initialize Database
    await init_db()

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

    # 3. Setup Webhook (if URL is provided)
    try:
        if settings.webhook_url:
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url != f"{settings.webhook_url}/webhook":
                await bot.set_webhook(url=f"{settings.webhook_url}/webhook")
                logger.info(f"Webhook set to {settings.webhook_url}/webhook")
        else:
            logger.warning("WEBHOOK_URL not set. Running in webhook mode requires a public URL.")
    except Exception as e:
        logger.error(f"Failed to setup Telegram webhook during startup: {e}")

    # 3. Setup Scheduled Jobs
    scheduler.add_job(process_thresholds, 'interval', minutes=10, args=[bot])
    scheduler.add_job(process_subscriptions, 'cron', hour=8, args=[bot, 'daily'])
    scheduler.add_job(process_subscriptions, 'interval', hours=1, args=[bot, 'hourly'])
    scheduler.start()

    yield

    # Shutdown logic
    scheduler.shutdown()
    if settings.webhook_url:
        await bot.delete_webhook()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Endpoint for Telegram to send updates to."""
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return Response(status_code=200)

@app.get("/api/diagnostics")
async def get_diagnostics():
    """Retrieve connection and network resolution diagnostic logs."""
    return {"diagnostics": diagnostic_results}

@app.get("/health")
async def health_check():
    """Health check endpoint required by Hugging Face Spaces."""
    return {"status": "ok"}

@app.get("/api/stats")
async def get_system_stats():
    """Retrieve database metrics and live LKR exchange rates."""
    stats = {}
    try:
        async with async_session() as session:
            # Gather subscriber (user) counts, subscriptions, and active thresholds
            users_count = await session.scalar(select(func.count(User.chat_id)))
            subs_count = await session.scalar(select(func.count(Subscription.id)))
            thresholds_count = await session.scalar(select(func.count(Threshold.id)).where(Threshold.is_active == True))
            
            stats["subscribers"] = users_count or 0
            stats["active_subscriptions"] = subs_count or 0
            stats["active_thresholds"] = thresholds_count or 0
            stats["db_status"] = "connected"
    except Exception as e:
        logger.error(f"Error fetching stats from DB: {e}")
        stats["subscribers"] = 0
        stats["active_subscriptions"] = 0
        stats["active_thresholds"] = 0
        stats["db_status"] = "error"

    # Fetch live exchange rates to LKR
    rates = {}
    currencies = ["USD", "EUR", "GBP", "AUD", "JPY"]
    for cur in currencies:
        try:
            rate = await fx_service.get_rate(cur, "LKR")
            rates[cur] = rate or 0.0
        except Exception as e:
            logger.error(f"Error fetching live rate for {cur}: {e}")
            rates[cur] = 0.0
            
    stats["rates"] = rates
    stats["system_status"] = "online"
    
    return stats

# Serve static dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get_dashboard():
    """Serves the premium dashboard index file."""
    return FileResponse("static/index.html")

