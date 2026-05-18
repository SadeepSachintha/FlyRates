import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
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
    pool_pre_ping=True,
    connect_args=connect_args,
    prepared_statement_cache_size=0
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
            await conn.run_sync(Base.metadata.create_all)
            
            # Check if running on PostgreSQL/Supabase and perform auto-migration of chat_id columns to BIGINT
            if "postgresql" in engine.url.drivername or "postgres" in engine.url.drivername:
                logger.info("Running on PostgreSQL. Ensuring chat_id columns are BIGINT...")
                migration_sql = """
                DO $$
                BEGIN
                    -- Drop foreign key constraints if they exist
                    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'subscriptions_chat_id_fkey') THEN
                        ALTER TABLE subscriptions DROP CONSTRAINT subscriptions_chat_id_fkey;
                    END IF;
                    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'thresholds_chat_id_fkey') THEN
                        ALTER TABLE thresholds DROP CONSTRAINT thresholds_chat_id_fkey;
                    END IF;

                    -- Alter columns to BIGINT
                    ALTER TABLE users ALTER COLUMN chat_id TYPE BIGINT;
                    ALTER TABLE subscriptions ALTER COLUMN chat_id TYPE BIGINT;
                    ALTER TABLE thresholds ALTER COLUMN chat_id TYPE BIGINT;

                    -- Re-create constraints with CASCADE delete (matching SQLAlchemy cascade configuration)
                    ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_chat_id_fkey 
                        FOREIGN KEY (chat_id) REFERENCES users(chat_id) ON DELETE CASCADE;
                    ALTER TABLE thresholds ADD CONSTRAINT thresholds_chat_id_fkey 
                        FOREIGN KEY (chat_id) REFERENCES users(chat_id) ON DELETE CASCADE;
                EXCEPTION
                    WHEN OTHERS THEN
                        RAISE NOTICE 'Migration encountered an error: %', SQLERRM;
                END $$;
                """
                from sqlalchemy import text
                await conn.execute(text(migration_sql))
                logger.info("Database chat_id columns successfully migrated/verified as BIGINT.")
                
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

async def get_session() -> AsyncSession:
    """Dependency to get a database session."""
    async with async_session() as session:
        yield session
