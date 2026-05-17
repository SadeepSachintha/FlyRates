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
    if len(args) not in [1, 2]:
        await message.answer("Usage: <code>/current &lt;base&gt; [target]</code>\nExample: <code>/current USD</code> or <code>/current USD EUR</code>", parse_mode="HTML")
        return

    base = args[0].upper()
    target = args[1].upper() if len(args) == 2 else "LKR"
    rate = await fx_service.get_rate(base, target)
    
    if rate:
        await message.answer(f"📈 Current Rate:\n1 {base} = {rate} {target}")
    else:
        await message.answer("❌ Failed to fetch rate. Please check if the currencies are supported or try again later.")

@router.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message):
    """Subscribes the user to periodic updates."""
    args = message.text.split()[1:]
    if len(args) not in [1, 2, 3]:
        await message.answer("Usage: <code>/subscribe &lt;base&gt; [target] [daily|hourly]</code>\nExample: <code>/subscribe USD daily</code>", parse_mode="HTML")
        return

    base = args[0].upper()
    
    if len(args) == 1:
        target = "LKR"
        freq = "daily"
    elif len(args) == 2:
        if args[1].lower() in ["daily", "hourly"]:
            target = "LKR"
            freq = args[1].lower()
        else:
            target = args[1].upper()
            freq = "daily"
    else:
        target = args[1].upper()
        freq = args[2].lower()

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
    if len(args) not in [3, 4]:
        await message.answer("Usage: <code>/threshold &lt;base&gt; [target] &lt;condition&gt; &lt;value&gt;</code>\nExample: <code>/threshold USD &lt; 300</code>", parse_mode="HTML")
        return

    if len(args) == 3:
        base, target, condition, value_str = args[0].upper(), "LKR", args[1], args[2]
    else:
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
        
    response = "📋 <b>Your Active Settings</b>\n\n"
    
    if subs:
        response += "🔔 <b>Subscriptions:</b>\n"
        for sub in subs:
            response += f"• {sub.base_currency} to {sub.target_currency} ({sub.frequency})\n"
    else:
        response += "🔔 <b>Subscriptions:</b> None\n"
        
    response += "\n"
    
    if thresholds:
        response += "🚨 <b>Thresholds:</b>\n"
        for th in thresholds:
            status = " (Active)" if th.is_active else " (Triggered/Inactive)"
            response += f"• {th.base_currency} to {th.target_currency} {th.condition} {th.target_value}{status}\n"
    else:
        response += "🚨 <b>Thresholds:</b> None\n"
        
    await message.answer(response, parse_mode="HTML")

@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: types.Message):
    """Removes a subscription."""
    args = message.text.split()[1:]
    if len(args) not in [1, 2]:
        await message.answer("Usage: <code>/unsubscribe &lt;base&gt; [target]</code>\nExample: <code>/unsubscribe USD</code>", parse_mode="HTML")
        return

    base = args[0].upper()
    target = args[1].upper() if len(args) == 2 else "LKR"
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
    if len(args) not in [1, 2]:
        await message.answer("Usage: <code>/delthreshold &lt;base&gt; [target]</code>\nExample: <code>/delthreshold USD</code>", parse_mode="HTML")
        return

    base = args[0].upper()
    target = args[1].upper() if len(args) == 2 else "LKR"
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
        "📚 <b>FlyRates Bot Help</b> 📚\n\n"
        "Here are the commands you can use:\n\n"
        "<b>Basic Commands</b>\n"
        "<code>/start</code> - Get welcome message\n"
        "<code>/help</code> - Show this help menu\n\n"
        "<b>Rates & Updates</b>\n"
        "<code>/current &lt;base&gt; [target]</code> - Get the live rate\n"
        "<code>/subscribe &lt;base&gt; [target] [daily/hourly]</code> - Automate updates\n"
        "<code>/threshold &lt;base&gt; [target] &lt;condition&gt; &lt;value&gt;</code> - Get custom alerts (&lt;, &gt;, &lt;=, &gt;=)\n\n"
        "<b>Management</b>\n"
        "<code>/mysubs</code> - View all your active subscriptions and alerts\n"
        "<code>/unsubscribe &lt;base&gt; [target]</code> - Remove a subscription\n"
        "<code>/delthreshold &lt;base&gt; [target]</code> - Remove an alert\n\n"
        f"<b>Supported Currencies:</b> {currencies_str}\n\n"
        "<b>Examples:</b>\n"
        "<code>/current USD</code> (defaults to LKR)\n"
        "<code>/subscribe USD daily</code>\n"
        "<code>/threshold USD &lt; 300</code>"
    )
    await message.answer(help_text, parse_mode="HTML")
