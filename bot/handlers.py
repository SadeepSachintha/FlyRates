from aiogram import Router, types
from aiogram.filters import Command
from services.fx_service import fx_service, ALLOWED_CURRENCIES
from db.session import get_session
from db.models import User, Subscription, Threshold
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Registers user and sends welcome message."""
    chat_id = message.chat.id
    # Create an async session explicitly since we're in a handler, not a FastAPI endpoint
    from db.session import async_session
    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()
        if not user:
            new_user = User(chat_id=chat_id)
            session.add(new_user)
            await session.commit()
            
    currencies_str = ", ".join(ALLOWED_CURRENCIES)
    await message.answer(
        f"Welcome to FlyRates! 🌍💸\n\n"
        f"I can track real-time exchange rates for you.\n"
        f"Supported Currencies: {currencies_str}\n\n"
        f"Commands:\n"
        f"/current <base> <target> - Get live rate (e.g., /current USD EUR)\n"
        f"/subscribe <base> <target> <daily/hourly> - Get automated updates\n"
        f"/threshold <base> <target> << or >> <value> - Get alerts (e.g., /threshold USD EUR < 0.90)"
    )

@router.message(Command("current"))
async def cmd_current(message: types.Message):
    """Fetches the current exchange rate."""
    args = message.text.split()[1:]
    if len(args) != 2:
        await message.answer("Usage: /current <base_currency> <target_currency>\nExample: /current USD EUR")
        return

    base, target = args[0].upper(), args[1].upper()
    rate = await fx_service.get_rate(base, target)
    
    if rate:
        await message.answer(f"📈 Current Rate:\n1 {base} = {rate} {target}")
    else:
        await message.answer("❌ Failed to fetch rate. Please check if the currencies are supported or try again later.")

@router.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message):
    """Subscribes the user to periodic updates."""
    args = message.text.split()[1:]
    if len(args) not in [2, 3]:
        await message.answer("Usage: /subscribe <base> <target> [daily|hourly]\nExample: /subscribe USD EUR daily")
        return

    base, target = args[0].upper(), args[1].upper()
    freq = args[2].lower() if len(args) == 3 else "daily"

    if not fx_service.is_valid_currency(base) or not fx_service.is_valid_currency(target):
        await message.answer("❌ Invalid currency pair.")
        return
        
    if freq not in ["daily", "hourly"]:
         await message.answer("❌ Frequency must be 'daily' or 'hourly'.")
         return

    from db.session import async_session
    async with async_session() as session:
        sub = Subscription(chat_id=message.chat.id, base_currency=base, target_currency=target, frequency=freq)
        session.add(sub)
        await session.commit()

    await message.answer(f"✅ Subscribed to {freq} updates for {base} to {target}.")

@router.message(Command("threshold"))
async def cmd_threshold(message: types.Message):
    """Sets a threshold alert."""
    args = message.text.split()[1:]
    if len(args) != 4:
        await message.answer("Usage: /threshold <base> <target> <condition> <value>\nExample: /threshold USD EUR < 0.90")
        return

    base, target, condition, value_str = args[0].upper(), args[1].upper(), args[2], args[3]
    
    try:
        value = float(value_str)
    except ValueError:
        await message.answer("❌ Value must be a number.")
        return

    if condition not in ['<', '>', '<=', '>=']:
        await message.answer("❌ Condition must be one of: <, >, <=, >=")
        return

    from db.session import async_session
    async with async_session() as session:
        threshold = Threshold(
            chat_id=message.chat.id, 
            base_currency=base, 
            target_currency=target, 
            condition=condition, 
            target_value=value
        )
        session.add(threshold)
        await session.commit()

    await message.answer(f"✅ Alert set! I will notify you when 1 {base} {condition} {value} {target}.")
