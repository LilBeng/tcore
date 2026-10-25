from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from functools import partial
from typing import DefaultDict

from tcore.models.coin import CoinSnapshot
from tcore.models.enums import MarketInterval, DataType, EventCode, ValueType
from tcore.utils.enums import Operator
from tcore.utils.indicator import sma


@dataclass(slots=True)
class StrategyData:
    symbols: str
    open_timestamp: datetime
    close_timestamp: datetime
    values: DefaultDict[MarketInterval, DefaultDict[ValueType, list[Decimal]]] = field(
        default_factory=partial(defaultdict, partial(defaultdict, list))
    )


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
    def get_value_changes(
            snapshot: CoinSnapshot,
            value_type: ValueType,
            interval: MarketInterval,
            length: int,
    ) -> list[Decimal]:

        if value_type in [ValueType.PRICE, ValueType.VOLUME_SMA_9]:
            data_type = DataType.KLINE
        elif value_type == ValueType.OPEN_INTEREST:
            data_type = DataType.OPEN_INTEREST
        elif value_type == ValueType.CVD:
            data_type = DataType.CVD
        elif value_type == ValueType.FUNDING_RATE:
            data_type = DataType.FUNDING_RATE
        else:
            return []

        values = []

        array = snapshot.aggregate(data_type, interval)
        if value_type == ValueType.VOLUME_SMA_9:
            array = sma([obj.volume for obj in array], 9)

        for obj in array[-length - 1:]:
            if value_type == ValueType.PRICE:
                values.append(obj.close)
            elif value_type == ValueType.VOLUME_SMA_9:
                values.append(obj)
            elif value_type == ValueType.OPEN_INTEREST:
                values.append(obj.single_open_interest)
            elif value_type == ValueType.CVD:
                values.append(obj.value)
            elif value_type == ValueType.FUNDING_RATE:
                values.append(obj.value)
            else:
                return []

        changes = []
        for previous, current in zip(values, values[1:]):
            if not previous:
                changes.append(Decimal(0))
            else:
                changes.append((current - previous) / previous * 100)
        return changes

    @property
    def open_timestamp(self) -> datetime:
        return self.close_timestamp - timedelta(minutes=self._interval.value)

    @abstractmethod
    def execute(self, snapshot: CoinSnapshot) -> EventCode:
        ...

    def get_data(
            self,
            snapshot: CoinSnapshot,
            intervals: tuple = (MarketInterval.M5, MarketInterval.M15, MarketInterval.M30, MarketInterval.H1),
            length: int = 1
    ) -> StrategyData:
        strategy_data = StrategyData(snapshot.symbol, self.open_timestamp, self.close_timestamp)
        for interval in intervals:
            for value_type in ValueType:
                strategy_data.values[interval][value_type] = self.get_value_changes(
                    snapshot,
                    value_type,
                    interval,
                    length
                )

        return strategy_data


class ShortStrategy(BaseStrategy):
    def __init__(self, interval: MarketInterval) -> None:
        super().__init__(interval)

        self._tracking: set[str] = set()

    def _check(
            self,
            snapshot: CoinSnapshot,
            value_type: ValueType,
            interval: MarketInterval,
            length: int,
            operator: Operator,
            base_value: int = 0
    ) -> bool:
        if values := self.get_value_changes(snapshot, value_type, interval, length):
            if len(values) < length:
                return False

            return all([operator.value(value, base_value) for value in values])

        return False

    def _check_grown(self, snapshot: CoinSnapshot) -> bool:
        # Проверка роста открытого интереса на сетке 15 минут (последние 5 значений)
        if not self._check(snapshot, ValueType.OPEN_INTEREST, MarketInterval.M15, 5, Operator.GE):
            return False

        # Проверка роста показателей последних значений на сетках 5, 15, 30, 60 минут
        # Проверка, что рост открытого интереса выше роста цены на сетках 5, 15, 30, 60 минут
        for interval in [MarketInterval.M5, MarketInterval.M15, MarketInterval.M30, MarketInterval.H1]:
            for value_type in [
                ValueType.PRICE,
                ValueType.VOLUME_SMA_9,
                ValueType.OPEN_INTEREST,
                ValueType.CVD,
                ValueType.FUNDING_RATE
            ]:
                if value_type == ValueType.CVD:
                    operator = Operator.GT
                else:
                    operator = Operator.GE

                if not self._check(snapshot, value_type, interval, 1, operator):
                    return False

            oi_changes = self.get_value_changes(snapshot, ValueType.OPEN_INTEREST, interval, 1)
            price_changes = self.get_value_changes(snapshot, ValueType.PRICE, interval, 1)
            for oi, price in zip(oi_changes, price_changes):
                if oi < price:
                    return False

        return True

    def _check_fall(self, snapshot: CoinSnapshot) -> bool:
        # Проверка падения показателей последних значений на сетках 15, 30 минут
        for interval in [MarketInterval.M15, MarketInterval.M30]:
            for value_type in [ValueType.VOLUME_SMA_9,  ValueType.CVD]:
                if not self._check(snapshot, value_type, interval, 1, Operator.LT):
                    return False

        return True

    def execute(self, snapshot: CoinSnapshot) -> EventCode:
        # Проверка на текущий интервал
        if not all(
                (
                        snapshot.validate(self.open_timestamp, DataType.KLINE, self.interval),
                        snapshot.validate(self.open_timestamp, DataType.CVD, self.interval),
                        snapshot.validate(self.close_timestamp, DataType.FUNDING_RATE, self.interval),
                        snapshot.validate(self.close_timestamp, DataType.OPEN_INTEREST, self.interval)
                )
        ):
            return EventCode.WAITING

        if snapshot.symbol in self._tracking:
            if self._check_fall(snapshot):
                self._tracking.remove(snapshot.symbol)

                return EventCode.TRADE
            else:
                if self._check_grown(snapshot):
                    return EventCode.GROWTH
                else:
                    self._tracking.remove(snapshot.symbol)

                    return EventCode.WAITING

        else:
            if self._check_grown(snapshot):
                self._tracking.add(snapshot.symbol)

                return EventCode.GROWTH
            else:
                return EventCode.WAITING
