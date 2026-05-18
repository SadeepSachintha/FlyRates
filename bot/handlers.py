import logging
import asyncio
from datetime import datetime
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.session import async_session
from db.models import User
from sqlalchemy import select
from services.fx_service import fx_service
from bot.scheduler import CURRENCIES, FLAGS, format_rates_list

logger = logging.getLogger(__name__)
router = Router()

def get_refresh_keyboard():
    """Generates the inline keyboard for rates list refresh."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Refresh Rates", callback_data="refresh_rates")
    return builder.as_markup()

async def get_formatted_current_rates() -> str:
    """Fetches the latest rates concurrently and formats the LKR list."""
    tasks = [fx_service.get_rate(cur, "LKR") for cur in CURRENCIES]
    rates_values = await asyncio.gather(*tasks)
    rates = dict(zip(CURRENCIES, rates_values))
    return format_rates_list(rates)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Greets the user and automatically subscribes them to daily updates."""
    chat_id = message.chat.id
    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(chat_id=chat_id, is_subscribed=True)
            session.add(user)
            await session.commit()
            text = (
                "🌍 <b>Welcome to FlyRates!</b> 🌍\n\n"
                "You have been successfully registered and subscribed to receive a <b>daily LKR exchange rate list</b>!\n\n"
                "Every morning at 8:00 AM UTC, you will receive a beautifully formatted list of all major currencies to Sri Lankan Rupee (LKR).\n\n"
                "🛠️ <b>Quick Commands:</b>\n"
                "• /current - Get the latest rate list instantly\n"
                "• /unsubscribe - Stop receiving daily updates\n"
                "• /help - Display the help guide"
            )
        else:
            if not user.is_subscribed:
                user.is_subscribed = True
                await session.commit()
                text = (
                    "🔄 <b>Welcome Back to FlyRates!</b>\n\n"
                    "Your subscription to the <b>daily exchange rate list updates</b> has been successfully reactivated!\n\n"
                    "🛠️ <b>Quick Commands:</b>\n"
                    "• /current - Get the latest rate list instantly\n"
                    "• /unsubscribe - Stop receiving daily updates"
                )
            else:
                text = (
                    "ℹ️ <b>You are already subscribed!</b>\n\n"
                    "You will receive a daily LKR exchange rate summary every morning.\n\n"
                    "🛠️ <b>Quick Commands:</b>\n"
                    "• /current - Get the latest rate list instantly\n"
                    "• /unsubscribe - Stop receiving daily updates"
                )
                
        await message.answer(text, parse_mode="HTML")

@router.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message):
    """Registers or re-enrolls a user in daily updates."""
    chat_id = message.chat.id
    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(chat_id=chat_id, is_subscribed=True)
            session.add(user)
            await session.commit()
            text = "✅ <b>Successfully Subscribed!</b>\n\nYou will now receive a daily LKR exchange rate list update every morning."
        elif not user.is_subscribed:
            user.is_subscribed = True
            await session.commit()
            text = "✅ <b>Subscription Activated!</b>\n\nYou will now receive a daily LKR exchange rate list update every morning."
        else:
            text = "ℹ️ <b>You are already subscribed to daily LKR updates!</b>"
            
        await message.answer(text, parse_mode="HTML")

@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: types.Message):
    """Opts out a user from daily broadcasts."""
    chat_id = message.chat.id
    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()
        
        if user and user.is_subscribed:
            user.is_subscribed = False
            await session.commit()
            text = (
                "❌ <b>Successfully Unsubscribed</b>\n\n"
                "You have opted-out of daily exchange rate updates. You will no longer receive daily broadcasts.\n\n"
                "💡 You can type /subscribe at any time to activate them again!"
            )
        else:
            text = (
                "ℹ️ <b>You are not currently subscribed.</b>\n\n"
                "💡 Type /subscribe if you wish to enroll in daily LKR rate updates."
            )
            
        await message.answer(text, parse_mode="HTML")

@router.message(Command("current"))
async def cmd_current(message: types.Message):
    """Instantly fetches and sends the LKR rate list with a Refresh button."""
    # Send a quick loading message so the user knows we are scraping/calculating
    loading_msg = await message.answer("🔄 <i>Fetching live rates from CBSL... Please wait.</i>", parse_mode="HTML")
    
    try:
        rates_text = await get_formatted_current_rates()
        await loading_msg.delete()
        await message.answer(rates_text, reply_markup=get_refresh_keyboard(), parse_mode="HTML")
    except Exception as e:
        logger.exception("Error serving /current:")
        await loading_msg.edit_text("⚠️ <i>Unable to fetch live rates at this time. Please try again later.</i>", parse_mode="HTML")

@router.callback_query(lambda c: c.data == "refresh_rates")
async def process_refresh_rates(callback_query: types.CallbackQuery):
    """Updates the LKR rate list message in-place if rates changed."""
    original_text = callback_query.message.text
    
    try:
        new_text = await get_formatted_current_rates()
        
        # Clean HTML tags for simple comparison since callback_query.message.text is raw text
        # aiogram's message.text strips HTML tags, so we can just compare content length or basic text
        # To be safe, we always update the message to reflect a new timestamp or show rate updates
        await callback_query.message.edit_text(
            new_text,
            reply_markup=get_refresh_keyboard(),
            parse_mode="HTML"
        )
        await callback_query.answer("Rates updated successfully!")
    except Exception as e:
        logger.error(f"Error handling inline refresh: {e}")
        await callback_query.answer("⚠️ Could not refresh rates right now.")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Displays a clean help manual for the bot."""
    text = (
        "📚 <b>FlyRates Bot Help Guide</b> 📚\n\n"
        "FlyRates is a single-purpose, high-availability exchange rate bot that sends a <b>daily summary of major global currencies converted to Sri Lankan Rupee (LKR)</b>.\n\n"
        "🛠️ <b>Available Commands:</b>\n"
        "• /subscribe - Subscribe to daily rate list updates\n"
        "• /unsubscribe - Opt-out of daily rate updates\n"
        "• /current - Retrieve the live exchange rates list instantly\n"
        "• /history - View weekly trends with beautiful visual sparklines\n"
        "• /help - Display this help manual\n\n"
        "🌍 <b>Supported Currencies:</b>\n"
        "USD, EUR, GBP, AUD, JPY, AED, SAR, INR, CNY, QAR\n\n"
        "🔄 <i>All rates are pulled live from the official Central Bank of Sri Lanka (CBSL).</i>"
    )
    await message.answer(text, parse_mode="HTML")

# --- WEEKLY HISTORICAL TRENDS & SPARKLINE SUPPORT ---

def generate_sparkline(values: list) -> str:
    """Generates a beautiful Unicode-based sparkline trend graph."""
    if not values:
        return ""
    minimum = min(values)
    maximum = max(values)
    rng = maximum - minimum
    if rng == 0:
        return "▆" * len(values)
    spark_chars = " ▂▃▄▅▆▇█"
    sparkline = []
    for v in values:
        idx = int((v - minimum) / rng * (len(spark_chars) - 1))
        sparkline.append(spark_chars[idx])
    return "".join(sparkline)

def get_history_keyboard():
    """Generates the inline keyboard for choosing a currency to view historical trends."""
    builder = InlineKeyboardBuilder()
    for cur in CURRENCIES:
        flag = FLAGS.get(cur, "💱")
        builder.button(text=f"{flag} {cur}", callback_data=f"hist_{cur}")
    builder.adjust(2)
    return builder.as_markup()

async def get_formatted_history(currency: str) -> str:
    """Queries history for a currency and formats a beautiful Telegram message with a sparkline."""
    from db.models import ExchangeRateHistory
    from sqlalchemy import select
    
    cur = currency.upper()
    async with async_session() as session:
        result = await session.execute(
            select(ExchangeRateHistory)
            .where(ExchangeRateHistory.currency == cur)
            .order_by(ExchangeRateHistory.timestamp.asc())
        )
        records = result.scalars().all()
        
        # Take last 7 records for weekly trend
        records = records[-7:]
        if not records:
            return f"⚠️ <b>No historical data available for {cur} yet.</b>\n\n💡 Try again after a daily rate update has occurred."
            
        initial_rate = records[0].rate_to_lkr
        latest_rate = records[-1].rate_to_lkr
        diff = latest_rate - initial_rate
        pct_change = (diff / initial_rate) * 100 if initial_rate > 0 else 0
        
        # Sparkline
        rates_list = [r.rate_to_lkr for r in records]
        sparkline = generate_sparkline(rates_list)
        
        flag = FLAGS.get(cur, "💱")
        direction_emoji = "📈" if diff >= 0 else "📉"
        trend_sign = "+" if diff >= 0 else ""
        
        lines = [
            f"{flag} <b>{cur} to LKR 7-Day Trend</b> {direction_emoji}",
            f"📅 <i>As of: {records[-1].timestamp.strftime('%Y-%m-%d')}</i>",
            "",
            f"📊 Sparkline: <code>[{sparkline}]</code>",
            "",
            "<b>Historical Rates:</b>"
        ]
        
        for r in records:
            dt_str = r.timestamp.strftime("%Y-%m-%d")
            lines.append(f"• {dt_str}: <b>{r.rate_to_lkr:.2f}</b> LKR")
            
        lines.extend([
            "",
            f"💵 Latest Rate: <b>{latest_rate:.2f} LKR</b>",
            f"🔄 7-day Change: <b>{trend_sign}{pct_change:.2f}% ({trend_sign}{diff:.2f} LKR)</b>"
        ])
        
        return "\n".join(lines)

@router.message(Command("history"))
async def cmd_history(message: types.Message):
    """Fetches and displays the weekly trend for a specific currency, or shows a selector keyboard."""
    args = message.text.split()
    if len(args) > 1:
        currency = args[1].upper()
        if currency not in CURRENCIES:
            supported = ", ".join(CURRENCIES)
            await message.answer(f"⚠️ <b>Unsupported currency!</b>\n\nSupported: {supported}", parse_mode="HTML")
            return
            
        loading_msg = await message.answer("🔄 <i>Generating weekly trend and sparkline...</i>", parse_mode="HTML")
        try:
            history_text = await get_formatted_history(currency)
            await loading_msg.delete()
            await message.answer(history_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error serving weekly trend for {currency}: {e}")
            await loading_msg.edit_text("⚠️ <i>Unable to retrieve historical trend at this time. Please try again.</i>", parse_mode="HTML")
    else:
        text = (
            "📈 <b>FlyRates Weekly Historical Trends</b> 📈\n\n"
            "View exchange rate performance and a visual trend sparkline over the last 7 days.\n\n"
            "👇 <b>Select a currency below to display the weekly trend:</b>"
        )
        await message.answer(text, reply_markup=get_history_keyboard(), parse_mode="HTML")

@router.callback_query(lambda c: c.data.startswith("hist_"))
async def process_history_callback(callback_query: types.CallbackQuery):
    """Processes interactive currency selections to load weekly rate history details."""
    currency = callback_query.data.split("_")[1]
    try:
        history_text = await get_formatted_history(currency)
        await callback_query.message.edit_text(
            history_text,
            reply_markup=get_history_keyboard(),
            parse_mode="HTML"
        )
        await callback_query.answer(f"Loaded weekly trend for {currency}!")
    except Exception as e:
        logger.error(f"Error handling history callback for {currency}: {e}")
        await callback_query.answer("⚠️ Could not load history details.")
