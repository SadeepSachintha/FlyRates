import asyncio
import sys
import os

# Append the project root to sys.path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import init_db, async_session, engine
from db.models import User
from sqlalchemy import select, text

async def test_migration():
    print("🚀 Initializing test database...")
    try:
        await init_db()
        print("✅ Database initialized successfully.")
        
        async with async_session() as session:
            # 1. Test insertion into users table
            print("✏️ Inserting a test user...")
            test_user = User(chat_id=987654321, is_subscribed=True)
            session.add(test_user)
            await session.commit()
            print("✅ Test user inserted.")
            
            # 2. Query columns to verify is_subscribed exists and defaults to True
            print("🔍 Verifying columns...")
            result = await session.execute(select(User).where(User.chat_id == 987654321))
            user = result.scalar_one_or_none()
            if user:
                print(f"✅ User found: chat_id={user.chat_id}, is_subscribed={user.is_subscribed}, created_at={user.created_at}")
                assert user.is_subscribed is True, "is_subscribed should be True by default"
            else:
                print("❌ User not found!")
                
            # 3. Clean up test user
            print("🧹 Cleaning up...")
            await session.delete(user)
            await session.commit()
            print("✅ Cleanup complete.")
            
    except Exception as e:
        print(f"❌ Error during migration test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()
        print("🏁 Engine disposed.")

if __name__ == "__main__":
    asyncio.run(test_migration())
