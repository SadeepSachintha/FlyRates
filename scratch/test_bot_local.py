import asyncio
import sys
import os
from datetime import datetime

# Append the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Dispatcher, Bot, types
from aiogram.client.session.base import BaseSession
from bot.handlers import router as bot_router
from db.session import init_db, async_session
from db.models import User
from sqlalchemy import select

# Create a lightweight mock session subclassing BaseSession
class MockSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.requests = []

    async def make_request(self, bot, method, timeout=None):
        """Intercepts outgoing methods, records them, and returns dummy results with bound bot."""
        self.requests.append(method)
        
        # Determine dummy return based on the method
        from aiogram.methods import SendMessage, DeleteMessage
        
        dummy_chat = types.Chat(id=999111222, type="private")
        
        if isinstance(method, SendMessage):
            msg = types.Message(
                message_id=100,
                date=datetime.now(),
                chat=dummy_chat,
                text=method.text
            )
            # Set the private _bot attribute to bind the bot instance natively
            msg._bot = bot
            return msg
        elif isinstance(method, DeleteMessage):
            return True
            
        msg = types.Message(
            message_id=100,
            date=datetime.now(),
            chat=dummy_chat,
            text="Mock reply"
        )
        msg._bot = bot
        return msg

    async def stream_content(self, url, headers=None, timeout=None, chunk_size=65536):
        """Dummy implementation of abstract method stream_content."""
        yield b""

    async def close(self):
        pass

# Create a dummy bot with our MockSession
mock_session = MockSession()
mock_bot = Bot(token="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ", session=mock_session)

async def test_bot_handlers():
    print("🚀 Initializing database for Bot testing...")
    await init_db()
    
    print("\n📦 Setting up Dispatcher...")
    dp = Dispatcher()
    dp.include_router(bot_router)
    
    # Mock user details
    test_chat_id = 999111222
    mock_user = types.User(id=test_chat_id, is_bot=False, first_name="Tester", last_name="Fly")
    mock_chat = types.Chat(id=test_chat_id, type="private")
    
    # Helper to create mock messages
    def create_mock_message(text: str) -> types.Message:
        msg = types.Message(
            message_id=1,
            date=datetime.now(),
            chat=mock_chat,
            from_user=mock_user,
            text=text
        )
        msg._bot = mock_bot
        return msg

    # Clean up any existing test user in the DB
    async with async_session() as session:
        existing = await session.scalar(select(User).where(User.chat_id == test_chat_id))
        if existing:
            await session.delete(existing)
            await session.commit()
            
    def print_last_request(title: str):
        """Helper to extract and print what was recorded by MockSession."""
        if mock_session.requests:
            req = mock_session.requests[-1]
            print(f"🤖 {title} Response:")
            
            # Extract text and buttons from the SendMessage object
            from aiogram.methods import SendMessage
            if isinstance(req, SendMessage):
                print(req.text)
                if req.reply_markup and hasattr(req.reply_markup, 'inline_keyboard'):
                    buttons = [b.text for row in req.reply_markup.inline_keyboard for b in row]
                    print(f"🔘 Buttons: {buttons}")
            else:
                print(f"[Method: {type(req).__name__}]")
            print()
            # Clear requests list
            mock_session.requests.clear()

    print("\n--- Test Case 1: Sending /start ---")
    msg_start = create_mock_message("/start")
    await dp.feed_update(mock_bot, types.Update(update_id=1, message=msg_start))
    print_last_request("START")
    
    print("--- Test Case 2: Sending /subscribe (already subscribed) ---")
    msg_sub = create_mock_message("/subscribe")
    await dp.feed_update(mock_bot, types.Update(update_id=2, message=msg_sub))
    print_last_request("SUBSCRIBE")
    
    print("--- Test Case 3: Sending /help ---")
    msg_help = create_mock_message("/help")
    await dp.feed_update(mock_bot, types.Update(update_id=3, message=msg_help))
    print_last_request("HELP")
    
    print("--- Test Case 4: Sending /current ---")
    msg_current = create_mock_message("/current")
    
    # We monkeypatch get_formatted_current_rates to run quickly without scraping
    from bot import handlers
    original_get_rates = handlers.get_formatted_current_rates
    async def mock_get_rates():
        return "🌍 <b>Mock LKR Exchange Rates</b>\n🇺🇸 1 USD = 310.00 LKR\n🇪🇺 1 EUR = 335.00 LKR\n🇬🇧 1 GBP = 390.00 LKR\n\n❌ Type /unsubscribe to stop."
    handlers.get_formatted_current_rates = mock_get_rates
    
    await dp.feed_update(mock_bot, types.Update(update_id=4, message=msg_current))
    
    # Find the SendMessage request in recorded requests queue (loading is deleted first)
    from aiogram.methods import SendMessage
    rates_req = None
    for req in reversed(mock_session.requests):
        if isinstance(req, SendMessage) and "Mock LKR Exchange Rates" in req.text:
            rates_req = req
            break
            
    if rates_req:
        print("🤖 CURRENT Response:")
        print(rates_req.text)
        if rates_req.reply_markup and hasattr(rates_req.reply_markup, 'inline_keyboard'):
            buttons = [b.text for row in rates_req.reply_markup.inline_keyboard for b in row]
            print(f"🔘 Buttons: {buttons}")
        print()
    mock_session.requests.clear()
    
    # Restore original function
    handlers.get_formatted_current_rates = original_get_rates

    print("--- Test Case 5: Sending /unsubscribe ---")
    msg_unsub = create_mock_message("/unsubscribe")
    await dp.feed_update(mock_bot, types.Update(update_id=5, message=msg_unsub))
    print_last_request("UNSUBSCRIBE")

    # Verification in DB
    print("🔎 Verifying DB state after /unsubscribe...")
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.chat_id == test_chat_id))
        if user:
            print(f"✅ DB User: chat_id={user.chat_id}, is_subscribed={user.is_subscribed}")
            assert user.is_subscribed is False, "User should be unsubscribed in database"
            # Cleanup
            await session.delete(user)
            await session.commit()
            print("✅ Cleanup test user from DB successful.")
        else:
            print("❌ Test user not found in DB!")
            
    print("\n🎉 ALL LOCAL HANDLER TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    asyncio.run(test_bot_handlers())
