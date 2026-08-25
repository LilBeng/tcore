from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from tcore.database.models import Base
from tcore.database.repositories import (
    CVDRepository,
    FundingRateRepository,
    KlineRepository,
    OpenInterestRepository
)


@dataclass(slots=True)
class Config:
    path: str

    @property
    def url(self) -> str:
        return f"sqlite+aiosqlite:///{self.path}"


class Database(object):
    def __init__(self, config: Config) -> None:
        self._engine: AsyncEngine = create_async_engine(
            config.url,
            connect_args={"timeout": 3},
        )

        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

        self.klines = KlineRepository(self._session_factory)
        self.open_interests = OpenInterestRepository(self._session_factory)
        self.funding_rates = FundingRateRepository(self._session_factory)
        self.cvds = CVDRepository(self._session_factory)

    async def initialize(self) -> None:
        async with self._engine.begin() as connection:
            await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
            await connection.exec_driver_sql("PRAGMA synchronous=NORMAL")
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()
