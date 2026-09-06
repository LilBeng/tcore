from typing import Optional

from tcore.database.database import MarketDataDB, UserDB
from tcore.database.writer import MarketDataDBWriter
from tcore.models.user import User, ExchangeAccount


class MarketDataService(object):
    def __init__(self, url: str, max_records: int, buffer_size: int, flush_interval: int) -> None:
        self.database = MarketDataDB(url, max_records)
        self.writer = MarketDataDBWriter(
            self.database.klines,
            self.database.open_interests,
            self.database.funding_rates,
            self.database.cvds,
            buffer_size,
            flush_interval
        )

    async def start(self) -> None:
        await self.database.initialize()
        await self.writer.start()

    async def stop(self) -> None:
        await self.writer.stop()
        await self.database.close()


class UserService(object):
    def __init__(self, url: str) -> None:
        self.database = UserDB(url)

    async def start(self) -> None:
        await self.database.initialize()

    async def stop(self) -> None:
        await self.database.close()

    async def add_user(self, user: User) -> User:
        return await self.database.users.add(user)

    async def get_user(self, user_id: int) -> Optional[User]:
        return await self.database.users.get(user_id)

    async def get_users(self) -> list[User]:
        return await self.database.users.get_users()

    async def update_user(self, user: User) -> None:
        await self.database.users.update(user)

    async def delete_user(self, user_id: int) -> None:
        await self.database.users.delete(user_id)

    async def add_exchange_account(self, account: ExchangeAccount) -> ExchangeAccount:
        return await self.database.exchange_accounts.add(account)

    async def get_exchange_account(self, account_id: int) -> Optional[ExchangeAccount]:
        return await self.database.exchange_accounts.get(account_id)

    async def get_user_exchange_account(self, user_id: int) -> Optional[ExchangeAccount]:
        return await self.database.exchange_accounts.get_by_user_id(user_id)

    async def update_exchange_account(self, account: ExchangeAccount) -> None:
        await self.database.exchange_accounts.update(account)

    async def delete_exchange_account(self, account_id: int) -> None:
        await self.database.exchange_accounts.delete(account_id)
