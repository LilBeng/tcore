from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from tcore.database.models import UserDB, ExchangeAccountDB
from tcore.models.user import User, ExchangeAccount


class UserRepository(object):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _to_entity(model: UserDB) -> User:
        return User(
            id=model.id,
            created_at=model.created_at,
            is_active=model.is_active,
            risk_percent=model.risk_percent,
            max_position_percent=model.max_position_percent,
            max_daily_loss_percent=model.max_daily_loss_percent,
            max_open_positions=model.max_open_positions
        )

    async def add(self, user: User) -> User:
        model = UserDB(
            is_active=user.is_active,
            risk_percent=user.risk_percent,
            max_position_percent=user.max_position_percent,
            max_daily_loss_percent=user.max_daily_loss_percent,
            max_open_positions=user.max_open_positions
        )

        async with self._session_factory() as session:
            session.add(model)
            await session.commit()
            await session.refresh(model)

        return self._to_entity(model)

    async def get(self, user_id: int) -> Optional[User]:
        async with self._session_factory() as session:
            model = await session.get(UserDB, user_id)

        return self._to_entity(model) if model else None # noqa

    async def update(self, user: User) -> None:
        if user.id is None:
            return

        async with self._session_factory() as session:
            model = await session.get(UserDB, user.id)

            if model is None:
                return

            model.is_active = user.is_active
            model.risk_percent = user.risk_percent
            model.max_position_percent = user.max_position_percent
            model.max_daily_loss_percent = user.max_daily_loss_percent
            model.max_open_positions = user.max_open_positions

            await session.commit()

    async def delete(self, user_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(UserDB).where(UserDB.id == user_id))
            await session.commit()

    async def get_users(self) -> list[User]:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(UserDB).order_by(UserDB.id)
            )
            models = result.all()

        return [self._to_entity(model) for model in models]


class ExchangeAccountRepository(object):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _to_entity(model: ExchangeAccountDB) -> ExchangeAccount:
        return ExchangeAccount(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            api_key=model.api_key,
            api_secret=model.api_secret,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    async def add(self, account: ExchangeAccount) -> ExchangeAccount:
        model = ExchangeAccountDB(
            user_id=account.user_id,
            name=account.name,
            api_key=account.api_key,
            api_secret=account.api_secret
        )

        async with self._session_factory() as session:
            session.add(model)
            await session.commit()
            await session.refresh(model)

        return self._to_entity(model)

    async def get(self, account_id: int) -> Optional[ExchangeAccount]:
        async with self._session_factory() as session:
            model = await session.get(
                ExchangeAccountDB,
                account_id
            )

        return self._to_entity(model) if model else None # noqa

    async def get_by_user_id(self, user_id: int) -> Optional[ExchangeAccount]:
        async with self._session_factory() as session:
            model = await session.scalar(
                select(ExchangeAccountDB)
                .where(ExchangeAccountDB.user_id == user_id)
            )

        return self._to_entity(model) if model else None

    async def update(self, account: ExchangeAccount) -> None:
        if account.id is None:
            return

        async with self._session_factory() as session:
            model = await session.get(
                ExchangeAccountDB,
                account.id
            )

            if model is None:
                return

            model.name = account.name
            model.api_key = account.api_key
            model.api_secret = account.api_secret

            await session.commit()

    async def delete(self, account_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(ExchangeAccountDB).where(
                    ExchangeAccountDB.id == account_id
                )
            )
            await session.commit()