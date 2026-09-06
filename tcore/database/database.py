from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from tcore.database.models import Base
from tcore.database.repositories import (
    CVDRepository,
    FundingRateRepository,
    KlineRepository,
    OpenInterestRepository
)
from tcore.database.repositories.user import UserRepository, ExchangeAccountRepository


class MarketDataDB(object):
    def __init__(self, url: str, max_records: int) -> None:
        self._engine: AsyncEngine = create_async_engine(url, connect_args={"timeout": 3})
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

        self.klines = KlineRepository(self._session_factory, max_records)
        self.open_interests = OpenInterestRepository(self._session_factory, max_records)
        self.funding_rates = FundingRateRepository(self._session_factory, max_records)
        self.cvds = CVDRepository(self._session_factory, max_records)

    async def initialize(self) -> None:
        async with self._engine.begin() as connection:
            await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
            await connection.exec_driver_sql("PRAGMA synchronous=NORMAL")
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()


class UserDB(object):
    def __init__(self, url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(url, connect_args={"timeout": 3})

        @event.listens_for(self._engine.sync_engine, "connect")
        def set_sqlite_pragma(connection, _) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

        self.users = UserRepository(self._session_factory)
        self.exchange_accounts = ExchangeAccountRepository(self._session_factory)

    async def initialize(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()
