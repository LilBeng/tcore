from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Boolean, ForeignKey, Integer, func, Float, DateTime
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tcore.database.decorators import DecimalType, TimestampType


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True


class KlineDB(Base):
    __tablename__ = "klines"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(TimestampType(), primary_key=True)

    open: Mapped[Decimal] = mapped_column(DecimalType())
    high: Mapped[Decimal] = mapped_column(DecimalType())
    low: Mapped[Decimal] = mapped_column(DecimalType())
    close: Mapped[Decimal] = mapped_column(DecimalType())
    volume: Mapped[Decimal] = mapped_column(DecimalType())
    turnover: Mapped[Decimal] = mapped_column(DecimalType())


class OpenInterestDB(Base):
    __tablename__ = "open_interests"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(TimestampType(), primary_key=True)

    open_interest: Mapped[Decimal] = mapped_column(DecimalType())
    single_open_interest: Mapped[Decimal] = mapped_column(DecimalType())


class FundingRateDB(Base):
    __tablename__ = "funding_rates"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(TimestampType(), primary_key=True)

    rate: Mapped[Decimal] = mapped_column(DecimalType())


class CVDDB(Base):
    __tablename__ = "cvds"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(TimestampType(), primary_key=True)

    value: Mapped[Decimal] = mapped_column(DecimalType())


class UserDB(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    risk_percent: Mapped[float] = mapped_column(Float, nullable=False)
    max_position_percent: Mapped[float] = mapped_column(Float, nullable=False)
    max_daily_loss_percent: Mapped[float] = mapped_column(Float, nullable=False)
    max_open_positions: Mapped[int] = mapped_column(Integer, nullable=False)


class ExchangeAccountDB(Base):
    __tablename__ = "exchange_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    api_key: Mapped[str] = mapped_column(String(512), nullable=False)
    api_secret: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
