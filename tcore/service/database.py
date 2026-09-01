from tcore.database.database import Database
from tcore.database.writer import DatabaseWriter
from tcore.models.config import DBServiceConfig


class DatabaseService(object):
    def __init__(self, config: DBServiceConfig) -> None:
        self.database = Database(config.url)
        self.writer = DatabaseWriter(
            self.database.klines,
            self.database.open_interests,
            self.database.funding_rates,
            self.database.cvds,
            config.buffer_size,
            config.flush_interval
        )

    async def start(self) -> None:
        await self.database.initialize()
        await self.writer.start()

    async def stop(self) -> None:
        await self.writer.stop()
        await self.database.close()
