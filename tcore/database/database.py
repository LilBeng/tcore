from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from tcore.database.models import Base


class Database:
    def __init__(self, url: str):
        self._engine = create_async_engine(url, echo=False)

        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def create_tables(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()
