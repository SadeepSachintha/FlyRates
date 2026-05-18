from sqlalchemy import Column, DateTime, Boolean, BigInteger, Integer, String, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    chat_id = Column(BigInteger, primary_key=True, index=True)
    is_subscribed = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class ExchangeRateHistory(Base):
    __tablename__ = "exchange_rate_history"

    id = Column(Integer, primary_key=True, index=True)
    currency = Column(String(3), nullable=False, index=True)
    rate_to_lkr = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)

