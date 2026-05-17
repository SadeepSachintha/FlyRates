import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test():
    try:
        engine = create_async_engine('postgresql+asyncpg://postgres.crysvmpozojurmskepyy:%21AT5%2C%238Phrs%2B6%216@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres')
        async with engine.begin() as conn:
            print("CONNECTION SUCCESSFUL")
    except Exception as e:
        print(f"CONNECTION FAILED: {type(e).__name__}: {e}")

asyncio.run(test())
