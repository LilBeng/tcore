from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from tcore.models.coin import CoinSnapshot, Data
from tcore.models.enums import MarketInterval, DataType, SignalStatus
from tcore.models.funding import FundingRate
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest


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

    @staticmethod
    def value_changes(array: list[Data], count: int = 1, **kwargs) -> list[Decimal]:
        values = []
        for obj in array[-count - 1:]:
            if isinstance(obj, Kline):
                if kwargs.get("is_turnover"):
                    values.append(obj.turnover)
                elif kwargs.get("is_volume"):
                    values.append(obj.volume)
                elif kwargs.get("is_price"):
                    values.append(obj.close)
            elif isinstance(obj, OpenInterest):
                values.append(obj.single_open_interest)
            elif isinstance(obj, FundingRate):
                values.append(obj.rate)
            else:
                values.append(obj.value)

        changes = []
        for previous, current in zip(values, values[1:]):
            if previous == 0:
                changes.append(Decimal(0))
            changes.append((current - previous) / previous * 100)
        return changes

    @property
    def open_timestamp(self) -> datetime:
        return self.close_timestamp - timedelta(minutes=self._interval.value)

    @abstractmethod
    def execute(self, snapshot: CoinSnapshot) -> SignalStatus:
        ...


class ShortStrategy(BaseStrategy):
    def __init__(self, interval: MarketInterval) -> None:
        super().__init__(interval)

        self._tracking: set[str] = set()

    def _get_values(
            self,
            snapshot: CoinSnapshot,
            data_type: DataType,
            interval: MarketInterval,
            length: int,
            **kwargs
    ) -> list[Decimal]:
        return self.value_changes(snapshot.aggregate(data_type, interval), length, **kwargs)

    def _check(
            self,
            snapshot: CoinSnapshot,
            data_type: DataType,
            interval: MarketInterval,
            length: int,
            is_up: bool,
            **kwargs
    ) -> bool:
        if values := self._get_values(snapshot, data_type, interval, length, **kwargs):
            if len(values) < length:
                return False

            if is_up:
                return all([value > 0 for value in values])
            else:
                return all([value < 0 for value in values])

        return False

    def _first_step(self, snapshot) -> bool:
        # Проверка роста открытого интереса на сетке 15 минут (последние 5 значений)
        if not self._check(snapshot, DataType.OPEN_INTEREST, MarketInterval.M15, 5, True):
            return False

        # Проверка роста показателей последних значений на сетках 5, 15, 30, 60 минут
        # Проверка, что рост открытого интереса выше роста цены на сетках 5, 15, 30, 60 минут
        for interval in [MarketInterval.M5, MarketInterval.M15, MarketInterval.M30, MarketInterval.H1]:
            oi_changes = []
            price_changes = []
            for data_type in DataType:
                if data_type == DataType.KLINE:
                    price_changes = self._get_values(snapshot, data_type, interval, 1, is_price=True)

                    if not self._check(snapshot, data_type, interval, 1, True, is_turnover=True):
                        return False
                else:
                    if data_type == DataType.OPEN_INTEREST:
                        oi_changes = self._get_values(snapshot, data_type, interval, 1, is_price=True)

                    if not self._check(snapshot, data_type, interval, 1, True):
                        return False

            for oi, price in zip(oi_changes, price_changes):
                if oi < price:
                    return False

        return True

    def _end_step(self, snapshot: CoinSnapshot) -> bool:
        # Проверка падения показателей последних значений на сетках 5, 15, 30 минут
        for interval in [MarketInterval.M5, MarketInterval.M15, MarketInterval.M30]:
            for data_type in [DataType.CVD, DataType.KLINE]:
                if data_type == DataType.KLINE:
                    if self._check(snapshot, data_type, interval, 1, False, is_turnover=True):
                        return False
                else:
                    if not self._check(snapshot, data_type, interval, 1, False):
                        return False

        return True

    def execute(self, snapshot: CoinSnapshot) -> SignalStatus:
        # Проверка на текущий интервал
        if not all(
                (
                        snapshot.validate(self.open_timestamp, DataType.KLINE, self.interval),
                        snapshot.validate(self.open_timestamp, DataType.CVD, self.interval),
                        snapshot.validate(self.close_timestamp, DataType.FUNDING_RATE, self.interval),
                        snapshot.validate(self.close_timestamp, DataType.OPEN_INTEREST, self.interval)
                )
        ):
            return SignalStatus.WAITING

        if snapshot.symbol in self._tracking:
            if self._end_step(snapshot):
                self._tracking.remove(snapshot.symbol)

                return SignalStatus.ENTRY
            else:
                if self._first_step(snapshot):
                    return SignalStatus.TRACKING
                else:
                    self._tracking.remove(snapshot.symbol)

                    return SignalStatus.NOT_SUITABLE

        else:
            if self._first_step(snapshot):
                self._tracking.add(snapshot.symbol)

                return SignalStatus.TRACKING
            else:
                return SignalStatus.NOT_SUITABLE
