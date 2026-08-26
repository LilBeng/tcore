from abc import abstractmethod
from datetime import datetime
from typing import Generic, TypeVar, Optional, Any

from sqlalchemy import delete, select, cast, BigInteger, func
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tcore.models.enums import MarketInterval

ModelT = TypeVar("ModelT")
EntityT = TypeVar("EntityT")


class BaseRepository(Generic[ModelT, EntityT]):
    model: type[ModelT]
    max_records: int = 150_000

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def _to_entity(self, model: ModelT) -> EntityT:
        raise NotImplementedError

    def _to_values(self, symbol: str, entity: EntityT) -> dict:
        raise NotImplementedError

    def _get_period(self, interval: MarketInterval) -> Any:
        period_ms = int(interval) * 60_000

        timestamp = cast(self.model.timestamp, BigInteger)

        return func.floor(timestamp / period_ms) * period_ms

    async def _trim(self, session: AsyncSession, symbol: str) -> None:
        subquery = (
            select(self.model.timestamp)
            .where(self.model.symbol == symbol)
            .order_by(self.model.timestamp.desc())
            .offset(self.max_records)
        )

        await session.execute(
            delete(self.model).where(
                self.model.symbol == symbol,
                self.model.timestamp.in_(subquery),
            )
        )

    async def add(self, symbol: str, entity: EntityT) -> None:
        await self.add_many(symbol, [entity])

    async def add_many(self, symbol: str, entities: list[EntityT]) -> None:
        if not entities:
            return None

        values = [self._to_values(symbol, entity) for entity in entities]

        async with self._session_factory() as session:
            await session.execute(
                insert(self.model).values(values)
            )

            await self._trim(session, symbol)

            await session.commit()

    async def upsert(self, symbol: str, entity: EntityT) -> None:
        await self.upsert_many(symbol, [entity])

    async def upsert_many(self, symbol: str, entities: list[EntityT]) -> None:
        if not entities:
            return None

        values = [self._to_values(symbol, entity) for entity in entities]

        statement = insert(self.model).values(values)

        update = {
            column.name: statement.excluded[column.name]
            for column in self.model.__table__.columns
            if column.name not in {"symbol", "timestamp"}
        }

        statement = statement.on_conflict_do_update(
            index_elements=["symbol", "timestamp"],
            set_=update
        )

        async with self._session_factory() as session:
            await session.execute(statement)

            await self._trim(session, symbol)

            await session.commit()

    async def get(self, symbol: str, limit: Optional[int] = None) -> list[EntityT]:
        async with self._session_factory() as session:
            statement = (
                select(self.model)
                .where(self.model.symbol == symbol)
                .order_by(self.model.timestamp.desc())
            )

            if limit is not None:
                statement = statement.limit(limit)

            result = await session.scalars(statement)
            models = list(result.all())

        models.reverse()

        return [self._to_entity(model) for model in models]

    @abstractmethod
    async def get_periods(self, symbol: str, interval: MarketInterval, limit: Optional[int] = None) -> list[EntityT]:
        raise NotImplementedError

    async def get_last(self, symbol: str) -> Optional[EntityT]:
        async with self._session_factory() as session:
            statement = (
                select(self.model)
                .where(self.model.symbol == symbol)
                .order_by(self.model.timestamp.desc())
                .limit(1)
            )

            model = await session.scalar(statement)

        return self._to_entity(model) if model else None

    async def get_range(self, symbol: str, start: datetime, end: datetime) -> list[EntityT]:
        async with self._session_factory() as session:
            statement = (
                select(self.model)
                .where(
                    self.model.symbol == symbol,
                    self.model.timestamp >= start,
                    self.model.timestamp < end
                )
                .order_by(self.model.timestamp)
            )

            result = await session.scalars(statement)
            models = result.all()

        return [self._to_entity(model) for model in models]

    async def delete_before(self, symbol: str, timestamp: datetime) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(self.model).where(
                    self.model.symbol == symbol,
                    self.model.timestamp < timestamp
                )
            )
            await session.commit()

    async def get_symbols(self) -> set[str]:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(self.model.symbol).distinct()
            )

            return set(result.all())
