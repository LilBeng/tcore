from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Iterable, TypeVar

from tcore.models.cvd import CVD
from tcore.models.enums import MarketInterval
from tcore.models.funding import FundingRate
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest

T = TypeVar("T")


class DataAggregator(object):
    @staticmethod
    def _period(timestamp: datetime, interval: MarketInterval) -> datetime:
        minute = timestamp.minute - timestamp.minute % interval

        return timestamp.replace(
            minute=minute,
            second=0,
            microsecond=0
        )

    @classmethod
    def _group(cls, data: Iterable[T], interval: MarketInterval) -> dict[datetime, list[T]]:
        periods: dict[datetime, list[T]] = defaultdict(list)

        for item in data:
            periods[cls._period(item.timestamp, interval)].append(item)

        return periods

    @classmethod
    def klines(cls, data: Iterable[Kline], interval: MarketInterval) -> list[Kline]:
        result = []

        for timestamp, items in cls._group(data, interval).items():
            result.append(
                Kline(
                    timestamp=timestamp,
                    open=items[0].open,
                    high=max(item.high for item in items),
                    low=min(item.low for item in items),
                    close=items[-1].close,
                    volume=sum((item.volume for item in items), Decimal(0)),
                    turnover=sum((item.turnover for item in items), Decimal(0))
                )
            )

        return result

    @classmethod
    def cvds(cls, data: Iterable[CVD], interval: MarketInterval) -> list[CVD]:
        result = []

        for timestamp, items in cls._group(data, interval).items():
            result.append(
                CVD(
                    timestamp=timestamp,
                    value=items[-1].value,
                    delta=sum((item.delta for item in items), Decimal(0))
                )
            )

        return result

    @classmethod
    def open_interests(cls, data: Iterable[OpenInterest], interval: MarketInterval) -> list[OpenInterest]:
        result = []

        for timestamp, items in cls._group(data, interval).items():
            item = items[0]

            result.append(
                OpenInterest(
                    timestamp=timestamp,
                    open_interest=item.open_interest,
                    single_open_interest=item.single_open_interest
                )
            )

        return result

    @classmethod
    def funding_rates(cls, data: Iterable[FundingRate], interval: MarketInterval) -> list[FundingRate]:
        result = []

        for timestamp, items in cls._group(data, interval).items():
            item = items[0]

            result.append(
                FundingRate(
                    timestamp=timestamp,
                    rate=item.rate
                )
            )

        return result
