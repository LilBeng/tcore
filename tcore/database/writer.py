import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import TypeAlias, Union, Optional

from tcore.database.repositories import (
    CVDRepository,
    FundingRateRepository,
    KlineRepository,
    OpenInterestRepository
)
from tcore.models.cvd import CVD
from tcore.models.funding import FundingRate
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest

logger = logging.getLogger(__name__)

Record: TypeAlias = Union[Kline, OpenInterest, FundingRate, CVD]


@dataclass(slots=True)
class DatabaseRecord:
    symbol: str
    data: Record


class MarketDataDBWriter(object):
    def __init__(
        self,
        kline_repository: KlineRepository,
        open_interest_repository: OpenInterestRepository,
        funding_rate_repository: FundingRateRepository,
        cvd_repository: CVDRepository,
        buffer_size: int = 60,
        flush_interval: float = 120
    ):
        self._repositories = {
            Kline: kline_repository,
            OpenInterest: open_interest_repository,
            FundingRate: funding_rate_repository,
            CVD: cvd_repository
        }

        self._buffer_size = buffer_size
        self._flush_interval = flush_interval

        self._queue: asyncio.Queue[DatabaseRecord] = asyncio.Queue()
        self._buffers: defaultdict[tuple[str, type[Record]], list[Record]] = defaultdict(list)

        self._task: Optional[asyncio.Task] = None

    def add(self, symbol: str, data: Record) -> None:
        self._queue.put_nowait(DatabaseRecord(symbol, data))

    async def flush(self, symbol: str) -> None:
        for (buffer_symbol, data_type), buffer in list(self._buffers.items()):
            if buffer_symbol != symbol or not buffer:
                continue

            await self._flush_buffer(buffer_symbol, data_type, buffer)

    async def start(self) -> None:
        if self._task is not None:
            return None

        self._task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        logger.info("Stopping Market values database writer... ")

        if self._task is None:
            return None

        await self._queue.join()
        await self._flush()

        self._task.cancel()

        try:
            await self._task
        except asyncio.CancelledError:
            pass

        self._task = None

    async def _worker(self) -> None:
        try:
            logger.info("Market values database writer started")
            while True:
                try:
                    record = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self._flush_interval
                    )
                except asyncio.TimeoutError:
                    await self._flush()
                    continue

                try:
                    await self._add_to_buffer(record)
                finally:
                    self._queue.task_done()

        except asyncio.CancelledError:
            raise

    async def _add_to_buffer(self, record: DatabaseRecord) -> None:
        key = (record.symbol, type(record.data))

        buffer = self._buffers[key]
        buffer.append(record.data)

        if len(buffer) >= self._buffer_size:
            await self._flush_buffer(record.symbol, type(record.data), buffer)

    async def _flush(self) -> None:
        logger.debug(f"Write {len(self._buffers)} values buffer to DB...")
        for (symbol, data_type), buffer in list(self._buffers.items()):
            if buffer:
                await self._flush_buffer(symbol, data_type, buffer)

    async def _flush_buffer(self, symbol: str, data_type: type[Record], buffer: list[Record]) -> None:
        logger.debug(f"Write to DB: symbol={symbol}, type={data_type.__name__}, records={len(buffer)}")

        repository = self._repositories[data_type]

        await repository.add_many(symbol, buffer)

        buffer.clear()
