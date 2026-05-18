import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from core.config import settings
from db.models import Base

import ssl

logger = logging.getLogger(__name__)

connect_args = {}
if "supabase" in settings.database_url or "postgres" in settings.database_url or "postgresql" in settings.database_url:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context
    connect_args["statement_cache_size"] = 0
    connect_args["prepared_statement_cache_size"] = 0

# Initialize the async engine
engine = create_async_engine(
    settings.database_url,
    echo=(settings.log_level == "DEBUG"),
    future=True,
    poolclass=NullPool,
    connect_args=connect_args
)

# Create an async session factory
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def init_db():
    """Initializes the database and creates all tables."""
    try:
        async with engine.begin() as conn:
            # 1. Create tables defined in models.py (creates users table if not exists)
            await conn.run_sync(Base.metadata.create_all)
            
            # 2. Database migrations and cleanups
            is_postgres = "postgresql" in engine.url.drivername or "postgres" in engine.url.drivername
            from sqlalchemy import text
            
            if is_postgres:
                logger.info("Running on PostgreSQL. Ensuring schema matches simplified design...")
                # Run each statement individually to comply with asyncpg single-statement execution rules
                await conn.execute(text("DROP TABLE IF EXISTS thresholds CASCADE"))
                await conn.execute(text("DROP TABLE IF EXISTS subscriptions CASCADE"))
                await conn.execute(text("ALTER TABLE users ALTER COLUMN chat_id TYPE BIGINT"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_subscribed BOOLEAN DEFAULT TRUE"))
                logger.info("PostgreSQL database schema successfully migrated and simplified.")
            else:
                logger.info("Running on SQLite. Running schema verification...")
                # SQLite fallback to add is_subscribed column if it does not exist
                try:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN is_subscribed BOOLEAN DEFAULT 1"))
                    logger.info("Successfully added is_subscribed column to SQLite users table.")
                except Exception:
                    # Column already exists
                    pass
                
        # 3. Dynamic Seeding of ExchangeRateHistory if empty
        async with async_session() as session:
            from sqlalchemy import select
            from db.models import ExchangeRateHistory
            from datetime import timedelta, timezone, datetime
            import random
            
            # Check if history exists
            result = await session.execute(select(ExchangeRateHistory.id).limit(1))
            if not result.first():
                logger.info("Exchange rate history table is empty. Generating 15-day random-walk seed data...")
                base_rates = {
                    "USD": 300.0,
                    "EUR": 325.0,
                    "GBP": 380.0,
                    "AUD": 200.0,
                    "JPY": 1.95,
                    "AED": 81.5,
                    "SAR": 80.0,
                    "INR": 3.60,
                    "CNY": 41.5,
                    "QAR": 82.0
                }
                
                now = datetime.now(timezone.utc)
                for cur, base_val in base_rates.items():
                    current_val = base_val
                    for day in range(15, -1, -1):
                        change = current_val * random.uniform(-0.012, 0.012)
                        current_val = round(current_val + change, 4)
                        dt = (now - timedelta(days=day)).replace(hour=8, minute=0, second=0, microsecond=0, tzinfo=None)
                        session.add(
                            ExchangeRateHistory(
                                currency=cur,
                                rate_to_lkr=current_val,
                                timestamp=dt
                            )
                        )
                await session.commit()
                logger.info("Successfully seeded 15-day historical exchange rates.")
                
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

async def get_session() -> AsyncSession:
    """Dependency to get a database session."""
    async with async_session() as session:
        yield session
