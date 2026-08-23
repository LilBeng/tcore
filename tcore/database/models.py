from datetime import datetime
from decimal import Decimal

from sqlalchemy import String
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
    delta: Mapped[Decimal] = mapped_column(DecimalType())
