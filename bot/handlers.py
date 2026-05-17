from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.fx_service import fx_service, ALLOWED_CURRENCIES
from db.session import get_session
from db.models import User, Subscription, Threshold
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)
router = Router()

# Flag mapping for clean and visual currency buttons
CURRENCY_FLAGS = {
    "USD": "🇺🇸",
    "GBP": "🇬🇧",
    "EUR": "🇪🇺",
    "AED": "🇦🇪",
    "SAR": "🇸🇦",
    "AUD": "🇦🇺",
    "INR": "🇮🇳",
    "JPY": "🇯🇵",
    "CNY": "🇨🇳",
    "QAR": "🇶🇦",
    "LKR": "🇱🇰"
}

def get_currency_text(currency_code: str) -> str:
    """Returns currency code prefixed with its country flag emoji."""
    flag = CURRENCY_FLAGS.get(currency_code.upper(), "🏳️")
    return f"{flag} {currency_code.upper()}"

async def ensure_user_registered(session, chat_id: int):
    """Automatically registers a user if they haven't run /start first."""
    result = await session.execute(select(User).where(User.chat_id == chat_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(chat_id=chat_id)
        session.add(user)
        await session.flush()
    return user

class ThresholdForm(StatesGroup):
    waiting_for_value = State()

def get_currency_keyboard(prefix: str, exclude: str = None, include_presets: bool = True, preset_action: str = "curr"):
    """
    Generates a keyboard with Quick Presets at the top and a Custom Grid below.
    - include_presets: if True, shows 1-Tap quick conversion to LKR buttons.
    - preset_action: 'curr' (current rate), 'sub' (subscribe), or 'th' (threshold).
    """
    builder = InlineKeyboardBuilder()
    
    # 1. Quick Presets (1-Tap Conversion to LKR)
    if include_presets and exclude != "LKR":
        presets = ["USD", "EUR", "GBP", "AUD"]
        # Filter presets to only those allowed
        valid_presets = [p for p in presets if p in ALLOWED_CURRENCIES]
        
        for base in valid_presets:
            if base == exclude:
                continue
            # Define standard preset target callbacks to LKR directly
            if preset_action == "curr":
                callback_data = f"curr_target:{base}:LKR"
            elif preset_action == "sub":
                callback_data = f"sub_target:{base}:LKR"
            else: # 'th'
                callback_data = f"th_target:{base}:LKR"
                
            flag_base = CURRENCY_FLAGS.get(base, "")
            flag_lkr = CURRENCY_FLAGS.get("LKR", "")
            builder.button(
                text=f"{flag_base} {base} ➡️ {flag_lkr} LKR", 
                callback_data=callback_data
            )
        builder.adjust(2) # Show presets in 2 columns
        
    # 2. Custom Grid (Grid of all currencies)
    grid_builder = InlineKeyboardBuilder()
    for curr in sorted(ALLOWED_CURRENCIES):
        if curr == exclude:
            continue
        grid_builder.button(text=get_currency_text(curr), callback_data=f"{prefix}:{curr}")
    grid_builder.adjust(4) # Custom grid in 4 columns
    
    # Combine builders
    builder.attach(grid_builder)
    
    # 3. Add Cancel button at the bottom row
    builder.row(types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action"))
    return builder.as_markup()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Registers user and sends welcome message."""
    chat_id = message.chat.id
    # Create an async session explicitly since we're in a handler, not a FastAPI endpoint
    from db.session import async_session
    async with async_session() as session:
        try:
            result = await session.execute(select(User).where(User.chat_id == chat_id))
            user = result.scalar_one_or_none()
            if not user:
                new_user = User(chat_id=chat_id)
                session.add(new_user)
                await session.commit()
        except Exception as e:
            logger.warning(f"Error or concurrent insert in cmd_start for {chat_id}: {e}")
            await session.rollback()
            
    currencies_str = ", ".join(ALLOWED_CURRENCIES)
    await message.answer(
        f"Welcome to FlyRates! 🌍💸\n\n"
        f"I can track real-time exchange rates for you.\n"
        f"Supported Currencies: {currencies_str}\n\n"
        f"Use /help to see all available commands!"
    )

@router.message(Command("current"))
async def cmd_current(message: types.Message):
    """Fetches the current exchange rate (direct or interactive)."""
    args = message.text.split()[1:]
    if not args:
        # Interactive mode
        reply_markup = get_currency_keyboard("curr_base", preset_action="curr")
        await message.answer(
            "💱 <b>Live Exchange Rates</b>\n\n"
            "Select a <b>Quick Preset</b> or select a custom <b>Base Currency</b> below:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return

    if len(args) not in [1, 2]:
        await message.answer(
            "Usage: <code>/current &lt;base&gt; [target]</code>\n"
            "Example: <code>/current USD</code> or <code>/current USD EUR</code>\n\n"
            "Or just type <code>/current</code> for interactive selection.", 
            parse_mode="HTML"
        )
        return

    base = args[0].upper()
    target = args[1].upper() if len(args) == 2 else "LKR"
    
    if not fx_service.is_valid_currency(base) or not fx_service.is_valid_currency(target):
        await message.answer(
            "❌ Invalid currency pair. Let's select interactively:", 
            reply_markup=get_currency_keyboard("curr_base", preset_action="curr")
        )
        return

    rate = await fx_service.get_rate(base, target)
    if rate:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Refresh", callback_data=f"curr_target:{base}:{target}")
        builder.button(text="⬅️ Change Currencies", callback_data="curr_start")
        builder.row(types.InlineKeyboardButton(text="❌ Close", callback_data="delete_message"))
        
        flag_base = CURRENCY_FLAGS.get(base, "")
        flag_target = CURRENCY_FLAGS.get(target, "")
        await message.answer(
            f"📈 <b>Current Rate:</b>\n"
            f"1 {flag_base} {base} = <b>{rate}</b> {flag_target} {target}\n\n"
            f"<i>Last updated: Just now</i>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Failed to fetch rate. Please try again later.")

# --- Global Callback Handlers ---

@router.callback_query(lambda c: c.data == "cancel_action")
async def callback_cancel_action(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Action cancelled.")
    await callback.answer()

@router.callback_query(lambda c: c.data == "delete_message")
async def callback_delete_message(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()

# --- Callback Handlers for Current Rates ---

@router.callback_query(lambda c: c.data == "curr_start")
async def callback_curr_start(callback: types.CallbackQuery):
    reply_markup = get_currency_keyboard("curr_base", preset_action="curr")
    await callback.message.edit_text(
        "💱 <b>Live Exchange Rates</b>\n\n"
        "Select a <b>Quick Preset</b> or select a custom <b>Base Currency</b> below:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("curr_base:"))
async def callback_curr_base(callback: types.CallbackQuery):
    base = callback.data.split(":")[1]
    # No presets for target selection, just select currency
    reply_markup = get_currency_keyboard(f"curr_target:{base}", exclude=base, include_presets=False)
    flag_base = CURRENCY_FLAGS.get(base, "")
    await callback.message.edit_text(
        f"💱 <b>Live Exchange Rates</b>\n\n"
        f"Base Currency: {flag_base} <b>{base}</b>\n\n"
        f"Select the <b>Target Currency</b>:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("curr_target:"))
async def callback_curr_target(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    base = parts[1]
    target = parts[2]
    
    rate = await fx_service.get_rate(base, target)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Refresh", callback_data=f"curr_target:{base}:{target}")
    builder.button(text="⬅️ Change Currencies", callback_data="curr_start")
    builder.row(types.InlineKeyboardButton(text="❌ Close", callback_data="delete_message"))
    
    from datetime import datetime
    time_str = datetime.now().strftime("%H:%M:%S")
    
    flag_base = CURRENCY_FLAGS.get(base, "")
    flag_target = CURRENCY_FLAGS.get(target, "")
    
    if rate:
        await callback.message.edit_text(
            f"📈 <b>Current Rate:</b>\n"
            f"1 {flag_base} {base} = <b>{rate}</b> {flag_target} {target}\n\n"
            f"<i>Last updated: {time_str} UTC</i>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ Failed to fetch rate. Let's try again:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

@router.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message):
    """Subscribes the user to periodic updates."""
    args = message.text.split()[1:]
    if not args:
        reply_markup = get_currency_keyboard("sub_base", preset_action="sub")
        await message.answer(
            "🔔 <b>Set Up Rate Subscription</b>\n\n"
            "Select a <b>Quick Preset</b> or select a custom <b>Base Currency</b> below:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return

    if len(args) not in [1, 2, 3]:
        await message.answer(
            "Usage: <code>/subscribe &lt;base&gt; [target] [daily|hourly]</code>\n"
            "Example: <code>/subscribe USD daily</code>\n\n"
            "Or just type <code>/subscribe</code> for interactive selection.", 
            parse_mode="HTML"
        )
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
        await message.answer(
            "❌ Invalid currency pair. Let's select interactively:",
            reply_markup=get_currency_keyboard("sub_base", preset_action="sub")
        )
        return
        
    if freq not in ["daily", "hourly"]:
        await message.answer("❌ Frequency must be 'daily' or 'hourly'.")
        return

    from db.session import async_session
    async with async_session() as session:
        await ensure_user_registered(session, message.chat.id)
        sub = Subscription(chat_id=message.chat.id, base_currency=base, target_currency=target, frequency=freq)
        session.add(sub)
        await session.commit()

    flag_base = CURRENCY_FLAGS.get(base, "")
    flag_target = CURRENCY_FLAGS.get(target, "")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Close", callback_data="delete_message")
    
    await message.answer(
        f"✅ <b>Subscribed!</b>\n"
        f"You will receive <b>{freq}</b> updates for {flag_base} {base} to {flag_target} {target}.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

# --- Callback Handlers for Subscriptions ---

@router.callback_query(lambda c: c.data == "sub_start")
async def callback_sub_start(callback: types.CallbackQuery):
    reply_markup = get_currency_keyboard("sub_base", preset_action="sub")
    await callback.message.edit_text(
        "🔔 <b>Set Up Rate Subscription</b>\n\n"
        "Select a <b>Quick Preset</b> or select a custom <b>Base Currency</b> below:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("sub_base:"))
async def callback_sub_base(callback: types.CallbackQuery):
    base = callback.data.split(":")[1]
    reply_markup = get_currency_keyboard(f"sub_target:{base}", exclude=base, include_presets=False)
    flag_base = CURRENCY_FLAGS.get(base, "")
    await callback.message.edit_text(
        f"🔔 <b>Set Up Rate Subscription</b>\n\n"
        f"Base Currency: {flag_base} <b>{base}</b>\n\n"
        f"Select the <b>Target Currency</b>:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("sub_target:"))
async def callback_sub_target(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    base = parts[1]
    target = parts[2]
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Daily (8:00 AM UTC)", callback_data=f"sub_freq:{base}:{target}:daily")
    builder.button(text="⏰ Hourly", callback_data=f"sub_freq:{base}:{target}:hourly")
    builder.row(types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action"))
    
    flag_base = CURRENCY_FLAGS.get(base, "")
    flag_target = CURRENCY_FLAGS.get(target, "")
    await callback.message.edit_text(
        f"🔔 <b>Set Up Rate Subscription</b>\n\n"
        f"Base: {flag_base} <b>{base}</b>\n"
        f"Target: {flag_target} <b>{target}</b>\n\n"
        f"Select the <b>Update Frequency</b>:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("sub_freq:"))
async def callback_sub_freq(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    base = parts[1]
    target = parts[2]
    freq = parts[3]
    
    from db.session import async_session
    async with async_session() as session:
        await ensure_user_registered(session, callback.message.chat.id)
        sub = Subscription(chat_id=callback.message.chat.id, base_currency=base, target_currency=target, frequency=freq)
        session.add(sub)
        await session.commit()
        
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Close", callback_data="delete_message")
    
    flag_base = CURRENCY_FLAGS.get(base, "")
    flag_target = CURRENCY_FLAGS.get(target, "")
    await callback.message.edit_text(
        f"✅ <b>Subscription Activated!</b>\n\n"
        f"You will receive <b>{freq}</b> updates for {flag_base} {base} to {flag_target} {target}.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(Command("threshold"))
async def cmd_threshold(message: types.Message):
    """Sets a threshold alert (direct or interactive)."""
    args = message.text.split()[1:]
    if not args:
        reply_markup = get_currency_keyboard("th_base", preset_action="th")
        await message.answer(
            "🚨 <b>Set Up Threshold Alert</b>\n\n"
            "Select a <b>Quick Preset</b> or select a custom <b>Base Currency</b> below:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return

    if len(args) not in [3, 4]:
        await message.answer(
            "Usage: <code>/threshold &lt;base&gt; [target] &lt;condition&gt; &lt;value&gt;</code>\n"
            "Example: <code>/threshold USD &lt; 300</code>\n\n"
            "Or just type <code>/threshold</code> for interactive setup.", 
            parse_mode="HTML"
        )
        return

    if len(args) == 3:
        base, target, condition, value_str = args[0].upper(), "LKR", args[1], args[2]
    else:
        base, target, condition, value_str = args[0].upper(), args[1].upper(), args[2], args[3]
    
    try:
        value = float(value_str)
    except ValueError:
        await message.answer("❌ Value must be a valid number.")
        return

    if condition not in ['<', '>', '<=', '>=']:
        await message.answer("❌ Condition must be one of: <, >, <=, >=")
        return

    if not fx_service.is_valid_currency(base) or not fx_service.is_valid_currency(target):
        await message.answer(
            "❌ Invalid currency pair. Let's select interactively:",
            reply_markup=get_currency_keyboard("th_base", preset_action="th")
        )
        return

    from db.session import async_session
    async with async_session() as session:
        await ensure_user_registered(session, message.chat.id)
        threshold = Threshold(
            chat_id=message.chat.id, 
            base_currency=base, 
            target_currency=target, 
            condition=condition, 
            target_value=value
        )
        session.add(threshold)
        await session.commit()

    flag_base = CURRENCY_FLAGS.get(base, "")
    flag_target = CURRENCY_FLAGS.get(target, "")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Close", callback_data="delete_message")
    
    await message.answer(
        f"✅ <b>Alert Set!</b>\n"
        f"I will notify you when 1 {flag_base} {base} {condition} <b>{value}</b> {flag_target} {target}.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

# --- Callback Handlers for Threshold Alerts ---

@router.callback_query(lambda c: c.data == "th_start")
async def callback_th_start(callback: types.CallbackQuery):
    reply_markup = get_currency_keyboard("th_base", preset_action="th")
    await callback.message.edit_text(
        "🚨 <b>Set Up Threshold Alert</b>\n\n"
        "Select a <b>Quick Preset</b> or select a custom <b>Base Currency</b> below:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("th_base:"))
async def callback_th_base(callback: types.CallbackQuery):
    base = callback.data.split(":")[1]
    reply_markup = get_currency_keyboard(f"th_target:{base}", exclude=base, include_presets=False)
    flag_base = CURRENCY_FLAGS.get(base, "")
    await callback.message.edit_text(
        f"🚨 <b>Set Up Threshold Alert</b>\n\n"
        f"Base Currency: {flag_base} <b>{base}</b>\n\n"
        f"Select the <b>Target Currency</b>:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("th_target:"))
async def callback_th_target(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    base = parts[1]
    target = parts[2]
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📈 Rises Above (>)", callback_data=f"th_cond:{base}:{target}:>")
    builder.button(text="📉 Drops Below (<)", callback_data=f"th_cond:{base}:{target}:<")
    builder.row(types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action"))
    
    flag_base = CURRENCY_FLAGS.get(base, "")
    flag_target = CURRENCY_FLAGS.get(target, "")
    await callback.message.edit_text(
        f"🚨 <b>Set Up Threshold Alert</b>\n\n"
        f"Base: {flag_base} <b>{base}</b>\n"
        f"Target: {flag_target} <b>{target}</b>\n\n"
        f"Select the <b>Alert Condition</b>:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("th_cond:"))
async def callback_th_cond(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    base = parts[1]
    target = parts[2]
    cond = parts[3]
    
    await state.set_state(ThresholdForm.waiting_for_value)
    await state.update_data(base=base, target=target, condition=cond, message_id=callback.message.message_id)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Cancel", callback_data="cancel_action")
    
    flag_base = CURRENCY_FLAGS.get(base, "")
    flag_target = CURRENCY_FLAGS.get(target, "")
    
    # Text instruction
    cond_name = "Rises Above" if cond == ">" else "Drops Below"
    await callback.message.edit_text(
        f"🚨 <b>Set Up Threshold Alert</b>\n\n"
        f"Base: {flag_base} <b>{base}</b>\n"
        f"Target: {flag_target} <b>{target}</b>\n"
        f"Condition: <b>{cond_name} ({cond})</b>\n\n"
        f"✍️ Please <b>type the target value</b> (e.g. 325.50) as a chat reply:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

# --- FSM Handler for Threshold Input Value ---

@router.message(ThresholdForm.waiting_for_value)
async def process_threshold_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    base = data.get("base")
    target = data.get("target")
    condition = data.get("condition")
    message_id = data.get("message_id")
    
    val_str = message.text.strip()
    try:
        value = float(val_str)
    except ValueError:
        # Prompt user to input again
        await message.answer("❌ Value must be a valid number. Please enter a valid decimal (e.g., 300.50) or click Cancel.")
        return
        
    from db.session import async_session
    async with async_session() as session:
        await ensure_user_registered(session, message.chat.id)
        threshold = Threshold(
            chat_id=message.chat.id, 
            base_currency=base, 
            target_currency=target, 
            condition=condition, 
            target_value=value
        )
        session.add(threshold)
        await session.commit()
        
    await state.clear()
    
    # Try deleting the interactive prompt message to keep the chat clean
    if message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=message_id)
        except Exception:
            pass
            
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Close", callback_data="delete_message")
    
    flag_base = CURRENCY_FLAGS.get(base, "")
    flag_target = CURRENCY_FLAGS.get(target, "")
    await message.answer(
        f"✅ <b>Alert Set Successfully!</b>\n\n"
        f"I will notify you when 1 {flag_base} {base} {condition} <b>{value}</b> {flag_target} {target}.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

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
        
    response = "📋 <b>Your Active Settings Dashboard</b>\n\n"
    
    if subs:
        response += "🔔 <b>Subscriptions:</b>\n"
        for sub in subs:
            flag_base = CURRENCY_FLAGS.get(sub.base_currency, "")
            flag_target = CURRENCY_FLAGS.get(sub.target_currency, "")
            response += f"• {flag_base} {sub.base_currency} ➡️ {flag_target} {sub.target_currency} (<i>{sub.frequency}</i>)\n"
    else:
        response += "🔔 <b>Subscriptions:</b> None\n"
        
    response += "\n"
    
    if thresholds:
        response += "🚨 <b>Threshold Alerts:</b>\n"
        for th in thresholds:
            status = " (Active)" if th.is_active else " (Triggered/Inactive)"
            flag_base = CURRENCY_FLAGS.get(th.base_currency, "")
            flag_target = CURRENCY_FLAGS.get(th.target_currency, "")
            response += f"• {flag_base} {th.base_currency} ➡️ {flag_target} {th.target_currency} <b>{th.condition} {th.target_value}</b><i>{status}</i>\n"
    else:
        response += "🚨 <b>Threshold Alerts:</b> None\n"
        
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Add Sub", callback_data="sub_start")
    builder.button(text="➕ Add Alert", callback_data="th_start")
    builder.row(
        types.InlineKeyboardButton(text="➖ Manage Subs", callback_data="unsub_start"),
        types.InlineKeyboardButton(text="➖ Manage Alerts", callback_data="delth_start")
    )
    builder.row(types.InlineKeyboardButton(text="❌ Close Dashboard", callback_data="delete_message"))
    
    await message.answer(response, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: types.Message):
    """Removes a subscription (direct or interactive)."""
    args = message.text.split()[1:]
    if not args:
        # Interactive unsubscribe
        from db.session import async_session
        async with async_session() as session:
            result = await session.execute(select(Subscription).where(Subscription.chat_id == message.chat.id))
            subs = result.scalars().all()
            
        if not subs:
            await message.answer("ℹ️ You don't have any active subscriptions to remove.")
            return
            
        builder = InlineKeyboardBuilder()
        for sub in subs:
            flag_base = CURRENCY_FLAGS.get(sub.base_currency, "")
            flag_target = CURRENCY_FLAGS.get(sub.target_currency, "")
            builder.button(
                text=f"❌ {flag_base} {sub.base_currency} ➡️ {flag_target} {sub.target_currency} ({sub.frequency})", 
                callback_data=f"unsub_id:{sub.id}"
            )
        builder.adjust(1)
        builder.row(types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action"))
        
        await message.answer(
            "➖ <b>Manage Subscriptions</b>\n\nClick on any subscription to remove it:", 
            reply_markup=builder.as_markup(), 
            parse_mode="HTML"
        )
        return

    if len(args) not in [1, 2]:
        await message.answer(
            "Usage: <code>/unsubscribe &lt;base&gt; [target]</code>\n"
            "Example: <code>/unsubscribe USD</code>\n\n"
            "Or just type <code>/unsubscribe</code> to list and remove.", 
            parse_mode="HTML"
        )
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

    flag_base = CURRENCY_FLAGS.get(base, "")
    flag_target = CURRENCY_FLAGS.get(target, "")
    await message.answer(f"✅ Unsubscribed from {flag_base} {base} to {flag_target} {target} updates.")

# --- Callback Handlers for Unsubscribing ---

@router.callback_query(lambda c: c.data == "unsub_start")
async def callback_unsub_start(callback: types.CallbackQuery):
    from db.session import async_session
    async with async_session() as session:
        result = await session.execute(select(Subscription).where(Subscription.chat_id == callback.message.chat.id))
        subs = result.scalars().all()
        
    if not subs:
        await callback.message.edit_text("ℹ️ You don't have any active subscriptions to remove.")
        await callback.answer()
        return
        
    builder = InlineKeyboardBuilder()
    for sub in subs:
        flag_base = CURRENCY_FLAGS.get(sub.base_currency, "")
        flag_target = CURRENCY_FLAGS.get(sub.target_currency, "")
        builder.button(
            text=f"❌ {flag_base} {sub.base_currency} ➡️ {flag_target} {sub.target_currency} ({sub.frequency})", 
            callback_data=f"unsub_id:{sub.id}"
        )
    builder.adjust(1)
    builder.row(types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action"))
    
    await callback.message.edit_text(
        "➖ <b>Manage Subscriptions</b>\n\nClick on any subscription to remove it:", 
        reply_markup=builder.as_markup(), 
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("unsub_id:"))
async def callback_unsub_id(callback: types.CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    
    from db.session import async_session
    async with async_session() as session:
        sub_result = await session.execute(select(Subscription).where(Subscription.id == sub_id))
        sub = sub_result.scalar_one_or_none()
        if sub:
            base = sub.base_currency
            target = sub.target_currency
            await session.delete(sub)
            await session.commit()
            
            builder = InlineKeyboardBuilder()
            builder.button(text="❌ Close", callback_data="delete_message")
            
            flag_base = CURRENCY_FLAGS.get(base, "")
            flag_target = CURRENCY_FLAGS.get(target, "")
            await callback.message.edit_text(
                f"✅ Unsubscribed from <b>{flag_base} {base}</b> to <b>{flag_target} {target}</b> updates.", 
                reply_markup=builder.as_markup(), 
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text("❌ Subscription not found or already deleted.")
    await callback.answer()

@router.message(Command("delthreshold"))
async def cmd_delthreshold(message: types.Message):
    """Removes a threshold alert (direct or interactive)."""
    args = message.text.split()[1:]
    if not args:
        # Interactive delthreshold
        from db.session import async_session
        async with async_session() as session:
            result = await session.execute(select(Threshold).where(Threshold.chat_id == message.chat.id))
            thresholds = result.scalars().all()
            
        if not thresholds:
            await message.answer("ℹ️ You don't have any active threshold alerts to remove.")
            return
            
        builder = InlineKeyboardBuilder()
        for th in thresholds:
            status = " (Active)" if th.is_active else " (Triggered)"
            flag_base = CURRENCY_FLAGS.get(th.base_currency, "")
            flag_target = CURRENCY_FLAGS.get(th.target_currency, "")
            builder.button(
                text=f"❌ {flag_base} {th.base_currency} ➡️ {flag_target} {th.target_currency} {th.condition} {th.target_value}{status}", 
                callback_data=f"delth_id:{th.id}"
            )
        builder.adjust(1)
        builder.row(types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action"))
        
        await message.answer(
            "➖ <b>Manage Threshold Alerts</b>\n\nClick on any alert to delete it:", 
            reply_markup=builder.as_markup(), 
            parse_mode="HTML"
        )
        return

    if len(args) not in [1, 2]:
        await message.answer(
            "Usage: <code>/delthreshold &lt;base&gt; [target]</code>\n"
            "Example: <code>/delthreshold USD</code>\n\n"
            "Or just type <code>/delthreshold</code> to list and delete.", 
            parse_mode="HTML"
        )
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

    flag_base = CURRENCY_FLAGS.get(base, "")
    flag_target = CURRENCY_FLAGS.get(target, "")
    await message.answer(f"✅ Deleted threshold alerts for {flag_base} {base} to {flag_target} {target}.")

# --- Callback Handlers for Deleting Thresholds ---

@router.callback_query(lambda c: c.data == "delth_start")
async def callback_delth_start(callback: types.CallbackQuery):
    from db.session import async_session
    async with async_session() as session:
        result = await session.execute(select(Threshold).where(Threshold.chat_id == callback.message.chat.id))
        thresholds = result.scalars().all()
        
    if not thresholds:
        await callback.message.edit_text("ℹ️ You don't have any active threshold alerts to remove.")
        await callback.answer()
        return
        
    builder = InlineKeyboardBuilder()
    for th in thresholds:
        status = " (Active)" if th.is_active else " (Triggered)"
        flag_base = CURRENCY_FLAGS.get(th.base_currency, "")
        flag_target = CURRENCY_FLAGS.get(th.target_currency, "")
        builder.button(
            text=f"❌ {flag_base} {th.base_currency} ➡️ {flag_target} {th.target_currency} {th.condition} {th.target_value}{status}", 
            callback_data=f"delth_id:{th.id}"
        )
    builder.adjust(1)
    builder.row(types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action"))
    
    await callback.message.edit_text(
        "➖ <b>Manage Threshold Alerts</b>\n\nClick on any alert to delete it:", 
        reply_markup=builder.as_markup(), 
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("delth_id:"))
async def callback_delth_id(callback: types.CallbackQuery):
    th_id = int(callback.data.split(":")[1])
    
    from db.session import async_session
    async with async_session() as session:
        th_result = await session.execute(select(Threshold).where(Threshold.id == th_id))
        th = th_result.scalar_one_or_none()
        if th:
            base = th.base_currency
            target = th.target_currency
            await session.delete(th)
            await session.commit()
            
            builder = InlineKeyboardBuilder()
            builder.button(text="❌ Close", callback_data="delete_message")
            
            flag_base = CURRENCY_FLAGS.get(base, "")
            flag_target = CURRENCY_FLAGS.get(target, "")
            await callback.message.edit_text(
                f"✅ Deleted threshold alert for <b>{flag_base} {base}</b> to <b>{flag_target} {target}</b>.", 
                reply_markup=builder.as_markup(), 
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text("❌ Threshold alert not found or already deleted.")
    await callback.answer()

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
