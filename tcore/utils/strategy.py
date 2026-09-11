from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta

from tcore.models.coin import CoinSnapshot
from tcore.models.enums import MarketInterval, DataType


class BaseStrategy(ABC):
    def __init__(self, interval: MarketInterval) -> None:
        self._interval = interval

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @property
    def interval(self) -> MarketInterval:
        return self._interval

    @property
    def close_timestamp(self) -> datetime:
        dt = datetime.now(timezone.utc)
        return dt.replace(
            minute=(dt.minute // self._interval.value) * self._interval.value,
            second=0, microsecond=0,
        )

    @property
    def open_timestamp(self) -> datetime:
        return self.close_timestamp - timedelta(minutes=self._interval.value)

    @abstractmethod
    def execute(self, snapshot: CoinSnapshot) -> bool:
        ...


class ShortStrategy(BaseStrategy):
    def __init__(self, interval: MarketInterval) -> None:
        super().__init__(interval)

        self._counts: dict[str, int] = {}

    def execute(self, snapshot: CoinSnapshot) -> bool:
        # Проверка на текущий интервал
        if not all(
                (
                        snapshot.validate(self.open_timestamp, DataType.KLINE, self.interval),
                        snapshot.validate(self.open_timestamp, DataType.CVD, self.interval),
                        snapshot.validate(self.close_timestamp, DataType.FUNDING_RATE, self.interval),
                        snapshot.validate(self.close_timestamp, DataType.OPEN_INTEREST, self.interval)
                )
        ):
            return False

        return True
