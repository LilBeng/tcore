from tcore.database.database import Database
from tcore.database.writer import DatabaseWriter


class DatabaseService(object):
    def __init__(self, url: str, max_records: int, buffer_size: int, flush_interval: int) -> None:
        self.database = Database(url, max_records)
        self.writer = DatabaseWriter(
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
