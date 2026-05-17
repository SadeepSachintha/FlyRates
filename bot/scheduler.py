import logging
from aiogram import Bot
from db.session import async_session
from db.models import Subscription, Threshold
from sqlalchemy import select
from services.fx_service import fx_service

logger = logging.getLogger(__name__)

async def process_subscriptions(bot: Bot, frequency: str):
    """Processes scheduled subscriptions."""
    logger.info(f"Processing {frequency} subscriptions...")
    async with async_session() as session:
        result = await session.execute(select(Subscription).where(Subscription.frequency == frequency))
        subscriptions = result.scalars().all()

        for sub in subscriptions:
            rate = await fx_service.get_rate(sub.base_currency, sub.target_currency)
            if rate:
                try:
                    await bot.send_message(
                        chat_id=sub.chat_id,
                        text=f"🔔 Scheduled Update ({frequency}):\n1 {sub.base_currency} = {rate} {sub.target_currency}"
                    )
                except Exception as e:
                    logger.error(f"Failed to send sub update to {sub.chat_id}: {e}")

async def process_thresholds(bot: Bot):
    """Processes active thresholds."""
    logger.info("Processing thresholds...")
    async with async_session() as session:
        result = await session.execute(select(Threshold).where(Threshold.is_active == True))
        thresholds = result.scalars().all()

        for thresh in thresholds:
            rate = await fx_service.get_rate(thresh.base_currency, thresh.target_currency)
            if rate is None:
                continue

            triggered = False
            if thresh.condition == '<' and rate < thresh.target_value:
                triggered = True
            elif thresh.condition == '>' and rate > thresh.target_value:
                triggered = True
            elif thresh.condition == '<=' and rate <= thresh.target_value:
                triggered = True
            elif thresh.condition == '>=' and rate >= thresh.target_value:
                triggered = True

            if triggered:
                try:
                    await bot.send_message(
                        chat_id=thresh.chat_id,
                        text=f"🚨 ALERT Triggered!\n\n1 {thresh.base_currency} is now {rate} {thresh.target_currency}\n(Condition: {thresh.condition} {thresh.target_value})"
                    )
                    # Deactivate the threshold after triggering to prevent spam
                    thresh.is_active = False
                    await session.commit()
                except Exception as e:
                    logger.error(f"Failed to send alert to {thresh.chat_id}: {e}")
