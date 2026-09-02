from bisect import bisect_left
from dataclasses import field, dataclass
from operator import attrgetter
from typing import Union

from tcore.models.cvd import CVD
from tcore.models.funding import FundingRate
from tcore.models.instrument import Instrument
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest
from tcore.models.tick import Ticker

Data = Union[Kline, OpenInterest, FundingRate, CVD]


@dataclass(slots=True)
class Coin:
    instrument: Instrument
    ticker: Ticker
    klines: list[Kline] = field(default_factory=list)
    open_interests: list[OpenInterest] = field(default_factory=list)
    funding_rates: list[FundingRate] = field(default_factory=list)
    cvds: list[CVD] = field(default_factory=list)
    max_len: int = 25_000

    def set_max_len(self, max_len: int) -> None:
        self.max_len = max_len

        self._trim(self.klines)
        self._trim(self.open_interests)
        self._trim(self.funding_rates)
        self._trim(self.cvds)

    def clear(self) -> None:
        self.klines.clear()
        self.open_interests.clear()
        self.funding_rates.clear()
        self.cvds.clear()

    def update_instrument(self, instrument: Instrument) -> None:
        self.instrument = instrument

    def update_ticker(self, ticker: Ticker) -> None:
        self.ticker = ticker

    def add_kline(self, kline: Kline) -> None:
        self._add(self.klines, kline)

    def add_open_interest(self, data: OpenInterest) -> None:
        self._add(self.open_interests, data)

    def add_funding_rate(self, data: FundingRate) -> None:
        self._add(self.funding_rates, data)

    def add_cvd(self, data: CVD) -> None:
        self._add(self.cvds, data)

    def extend_klines(self, data: list[Kline]) -> None:
        self.klines = self._merge(self.klines, data)

    def extend_open_interests(self, data: list[OpenInterest]) -> None:
        self.open_interests = self._merge(self.open_interests, data)

    def extend_funding_rates(self, data: list[FundingRate]) -> None:
        self.funding_rates = self._merge(self.funding_rates, data)

    def extend_cvds(self, data: list[CVD]) -> None:
        self.cvds = self._merge(self.cvds, data)

    def _trim(self, data: list[Data]) -> None:
        if len(data) > self.max_len:
            del data[:-self.max_len]

    def _add(self, data: list[Data], obj: Data) -> None:
        if not data or obj.timestamp > data[-1].timestamp:
            data.append(obj)
        elif obj.timestamp == data[-1].timestamp:
            data[-1] = obj
        else:
            timestamps = [item.timestamp for item in data]
            pos = bisect_left(timestamps, obj.timestamp)

            if pos < len(data) and data[pos].timestamp == obj.timestamp:
                data[pos] = obj
            else:
                data.insert(pos, obj)

        self._trim(data)

    def _merge(self, data: list[Data], items: list[Data]) -> list[Data]:
        result = self._sorted(data, items)
        return result[-self.max_len:]

    @staticmethod
    def _sorted(data: list[Data], items: list[Data]) -> list[Data]:
        values = {item.timestamp: item for item in data}

        for item in items:
            values[item.timestamp] = item

        return sorted(values.values(), key=attrgetter("timestamp"))
