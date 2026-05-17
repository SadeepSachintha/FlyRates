import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings
from db.session import init_db
from bot.handlers import router as bot_router
from bot.scheduler import process_subscriptions, process_thresholds

# Configure Logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# Initialize Aiogram
bot = Bot(token=settings.bot_token)
dp = Dispatcher()
dp.include_router(bot_router)

# Initialize Scheduler
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize Database
    await init_db()

    # 2. Setup Webhook (if URL is provided)
    if settings.webhook_url:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url != f"{settings.webhook_url}/webhook":
            await bot.set_webhook(url=f"{settings.webhook_url}/webhook")
            logger.info(f"Webhook set to {settings.webhook_url}/webhook")
    else:
        logger.warning("WEBHOOK_URL not set. Running in webhook mode requires a public URL.")

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

@app.get("/health")
async def health_check():
    """Health check endpoint required by Hugging Face Spaces."""
    return {"status": "ok"}
