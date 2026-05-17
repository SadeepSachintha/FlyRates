import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import settings
from db.models import Base

logger = logging.getLogger(__name__)

# Initialize the async engine
engine = create_async_engine(
    settings.database_url,
    echo=(settings.log_level == "DEBUG"),
    future=True,
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
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

async def get_session() -> AsyncSession:
    """Dependency to get a database session."""
    async with async_session() as session:
        yield session
