import logging
import asyncio
from datetime import datetime
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError
from db.session import async_session
from db.models import User
from sqlalchemy import select
from services.fx_service import fx_service

logger = logging.getLogger(__name__)

CURRENCIES = ["USD", "EUR", "GBP", "AUD", "JPY", "AED", "SAR", "INR", "CNY", "QAR"]

FLAGS = {
    "USD": "🇺🇸",
    "EUR": "🇪🇺",
    "GBP": "🇬🇧",
    "AUD": "🇦🇺",
    "JPY": "🇯🇵",
    "AED": "🇦🇪",
    "SAR": "🇸🇦",
    "INR": "🇮🇳",
    "CNY": "🇨🇳",
    "QAR": "🇶🇦"
}

def format_rates_list(rates: dict) -> str:
    """Formats the rates dictionary into a beautifully styled HTML message."""
    lines = [
        "🌍 <b>Daily LKR Exchange Rates</b> 🌍",
        "<i>Brought to you by SS Labz</i>",
        f"📅 <i>Date: {datetime.now().strftime('%Y-%m-%d')}</i>",
        ""
    ]
    for cur in CURRENCIES:
        rate = rates.get(cur)
        flag = FLAGS.get(cur, "💱")
        if rate:
            lines.append(f"{flag} <b>1 {cur}</b> = {rate:.2f} LKR")
        else:
            lines.append(f"{flag} <b>1 {cur}</b> = <i>Scraper Offline</i>")
            
    lines.extend([
        "",
        "🔄 <i>Rates are sourced directly from the Central Bank of Sri Lanka (CBSL).</i>",
        "❌ Type /unsubscribe to opt-out of these daily updates."
    ])
    return "\n".join(lines)

async def process_daily_broadcast(bot: Bot):
    """Processes the scheduled daily broadcast to all subscribed users."""
    logger.info("Starting daily exchange rate broadcast...")
    
    # 1. Fetch all exchange rates concurrently
    tasks = [fx_service.get_rate(cur, "LKR") for cur in CURRENCIES]
    rates_values = await asyncio.gather(*tasks)
    rates = dict(zip(CURRENCIES, rates_values))
    
    # 2. Format the message
    broadcast_message = format_rates_list(rates)
    
    # 3. Retrieve all active subscribers
    async with async_session() as session:
        result = await session.execute(select(User.chat_id).where(User.is_subscribed == True))
        subscribers = result.scalars().all()
        
        if not subscribers:
            logger.info("No active subscribers found for daily broadcast.")
            return
            
        logger.info(f"Broadcasting to {len(subscribers)} active subscribers...")
        
        # 4. Deliver updates
        for chat_id in subscribers:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=broadcast_message,
                    parse_mode="HTML"
                )
                logger.info(f"Daily broadcast sent successfully to chat_id: {chat_id}")
            except TelegramForbiddenError:
                # User blocked the bot - deactivate subscription to save future API limits
                logger.warning(f"User {chat_id} has blocked the bot. Opting them out of daily updates...")
                user_res = await session.execute(select(User).where(User.chat_id == chat_id))
                user_obj = user_res.scalar_one_or_none()
                if user_obj:
                    user_obj.is_subscribed = False
                    await session.commit()
            except TelegramAPIError as e:
                logger.error(f"Telegram API error when broadcasting to {chat_id}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error when broadcasting to {chat_id}: {e}")
                
    logger.info("Daily exchange rate broadcast completed successfully.")
