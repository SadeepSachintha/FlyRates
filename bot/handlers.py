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
        f"Use /help to see all available commands!"
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

@router.message(Command("mysubs"))
async def cmd_mysubs(message: types.Message):
    """Lists all active subscriptions and thresholds for the user."""
    from db.session import async_session
    chat_id = message.chat.id
    
    async with async_session() as session:
        subs_result = await session.execute(select(Subscription).where(Subscription.chat_id == chat_id))
        subs = subs_result.scalars().all()
        
        thresholds_result = await session.execute(select(Threshold).where(Threshold.chat_id == chat_id))
        thresholds = thresholds_result.scalars().all()
        
    response = "📋 **Your Active Settings**\n\n"
    
    if subs:
        response += "🔔 **Subscriptions:**\n"
        for sub in subs:
            response += f"• {sub.base_currency} to {sub.target_currency} ({sub.frequency})\n"
    else:
        response += "🔔 **Subscriptions:** None\n"
        
    response += "\n"
    
    if thresholds:
        response += "🚨 **Thresholds:**\n"
        for th in thresholds:
            status = " (Active)" if th.is_active else " (Triggered/Inactive)"
            response += f"• {th.base_currency} to {th.target_currency} {th.condition} {th.target_value}{status}\n"
    else:
        response += "🚨 **Thresholds:** None\n"
        
    await message.answer(response, parse_mode="Markdown")

@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: types.Message):
    """Removes a subscription."""
    args = message.text.split()[1:]
    if len(args) != 2:
        await message.answer("Usage: /unsubscribe <base> <target>\nExample: /unsubscribe USD EUR")
        return

    base, target = args[0].upper(), args[1].upper()
    chat_id = message.chat.id

    from db.session import async_session
    async with async_session() as session:
        result = await session.execute(select(Subscription).where(
            Subscription.chat_id == chat_id,
            Subscription.base_currency == base,
            Subscription.target_currency == target
        ))
        subs = result.scalars().all()
        
        if not subs:
            await message.answer(f"❌ You don't have a subscription for {base} to {target}.")
            return
            
        for sub in subs:
            await session.delete(sub)
        await session.commit()

    await message.answer(f"✅ Unsubscribed from {base} to {target} updates.")

@router.message(Command("delthreshold"))
async def cmd_delthreshold(message: types.Message):
    """Removes a threshold alert."""
    args = message.text.split()[1:]
    if len(args) != 2:
        await message.answer("Usage: /delthreshold <base> <target>\nExample: /delthreshold USD EUR")
        return

    base, target = args[0].upper(), args[1].upper()
    chat_id = message.chat.id

    from db.session import async_session
    async with async_session() as session:
        result = await session.execute(select(Threshold).where(
            Threshold.chat_id == chat_id,
            Threshold.base_currency == base,
            Threshold.target_currency == target
        ))
        thresholds = result.scalars().all()
        
        if not thresholds:
            await message.answer(f"❌ You don't have a threshold alert for {base} to {target}.")
            return
            
        for th in thresholds:
            await session.delete(th)
        await session.commit()

    await message.answer(f"✅ Deleted threshold alerts for {base} to {target}.")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Shows detailed usage instructions."""
    currencies_str = ", ".join(ALLOWED_CURRENCIES)
    help_text = (
        "📚 **FlyRates Bot Help** 📚\n\n"
        "Here are the commands you can use:\n\n"
        "**Basic Commands**\n"
        "`/start` - Get welcome message\n"
        "`/help` - Show this help menu\n\n"
        "**Rates & Updates**\n"
        "`/current <base> <target>` - Get the live rate\n"
        "`/subscribe <base> <target> [daily/hourly]` - Automate updates\n"
        "`/threshold <base> <target> <condition> <value>` - Get custom alerts (<, >, <=, >=)\n\n"
        "**Management**\n"
        "`/mysubs` - View all your active subscriptions and alerts\n"
        "`/unsubscribe <base> <target>` - Remove a subscription\n"
        "`/delthreshold <base> <target>` - Remove an alert\n\n"
        f"**Supported Currencies:** {currencies_str}\n\n"
        "**Examples:**\n"
        "`/current USD EUR`\n"
        "`/subscribe USD EUR hourly`\n"
        "`/threshold USD EUR < 0.90`"
    )
    await message.answer(help_text, parse_mode="Markdown")
