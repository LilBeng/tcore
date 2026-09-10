from abc import ABC, abstractmethod
from datetime import datetime, timezone

from tcore.models.coin import CoinSnapshot
from tcore.models.enums import MarketInterval


class BaseStrategy(ABC):
    def __init__(self, interval: MarketInterval) -> None:
        self._interval = interval

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @property
    def timestamp(self) -> datetime:
        dt = datetime.now(timezone.utc)
        return dt.replace(
            minute=(dt.minute // self._interval.value) * self._interval.value,
            second=0, microsecond=0,
        )

    @abstractmethod
    def execute(self, snapshot: CoinSnapshot) -> bool:
        ...
