from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, BigInteger
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    chat_id = Column(BigInteger, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    thresholds = relationship("Threshold", back_populates="user", cascade="all, delete-orphan")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, ForeignKey("users.chat_id"))
    base_currency = Column(String(3), nullable=False)
    target_currency = Column(String(3), nullable=False)
    # Frequency could be 'daily', 'hourly'
    frequency = Column(String(20), default="daily")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    user = relationship("User", back_populates="subscriptions")

class Threshold(Base):
    __tablename__ = "thresholds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, ForeignKey("users.chat_id"))
    base_currency = Column(String(3), nullable=False)
    target_currency = Column(String(3), nullable=False)
    condition = Column(String(5), nullable=False) # e.g., '<', '>', '<=', '>='
    target_value = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    user = relationship("User", back_populates="thresholds")
