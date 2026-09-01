from bisect import bisect_left
from collections import deque
from dataclasses import field, dataclass
from operator import attrgetter
from typing import Union

from tcore.models.cvd import CVD
from tcore.models.funding import FundingRate
from tcore.models.instrument import Instrument
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest
from tcore.models.tick import Ticker


@dataclass(slots=True)
class Coin:
    instrument: Instrument
    ticker: Ticker
    klines: deque[Kline] = field(default_factory=deque)
    open_interests: deque[OpenInterest] = field(default_factory=deque)
    funding_rates: deque[FundingRate] = field(default_factory=deque)
    cvds: deque[CVD] = field(default_factory=deque)

    def set_max_len(self, max_len: int) -> None:
        self.klines = deque(self.klines, maxlen=max_len)
        self.open_interests = deque(self.open_interests, maxlen=max_len)
        self.funding_rates = deque(self.funding_rates, maxlen=max_len)
        self.cvds = deque(self.cvds, maxlen=max_len)

    def clear(self) -> None:
        self.klines.clear()
        self.open_interests.clear()
        self.funding_rates.clear()
        self.cvds.clear()

    @staticmethod
    def _add(queue: deque, obj: Union[Ticker, Kline, FundingRate, OpenInterest, CVD]) -> None:
        timestamps = [k.timestamp for k in queue]
        pos = bisect_left(timestamps, obj.timestamp)

        if pos < len(queue) and queue[pos].timestamp == obj.timestamp:
            queue[pos] = obj
        else:
            queue.insert(pos, obj)

            while len(queue) > queue.maxlen:
                queue.popleft()

    @staticmethod
    def _sorted(queue: deque, objs: list[Union[Ticker, Kline, FundingRate, OpenInterest, CVD]]):
        existing_dict = {k.timestamp: k for k in queue}

        for obj in objs:
            existing_dict[obj.timestamp] = obj

        return sorted(existing_dict.values(), key=attrgetter('timestamp'))

    def update_instrument(self, instrument: Instrument) -> None:
        self.instrument = instrument

    def update_ticker(self, ticker: Ticker) -> None:
        self.ticker = ticker

    def add_kline(self, kline: Kline) -> None:
        self._add(self.klines, kline)

    def extend_klines(self, klines: list[Kline]) -> None:
        self.klines = deque(
            self._sorted(self.klines, klines),
            maxlen=self.klines.maxlen
        )

    def add_open_interest(self, open_interest: OpenInterest) -> None:
        self._add(self.open_interests, open_interest)

    def extend_open_interests(self, open_interests: list[OpenInterest]) -> None:
        self.open_interests = deque(
            self._sorted(self.open_interests, open_interests),
            maxlen=self.open_interests.maxlen
        )

    def add_funding_rate(self, funding_rate: FundingRate) -> None:
        self._add(self.funding_rates, funding_rate)

    def extend_funding_rates(self, funding_rates: list[FundingRate]) -> None:
        self.funding_rates = deque(
            self._sorted(self.funding_rates, funding_rates),
            maxlen=self.funding_rates.maxlen
        )

    def add_cvd(self, cvd: CVD) -> None:
        self._add(self.cvds, cvd)

    def extend_cvds(self, cvds: list[CVD]) -> None:
        self.cvds = deque(
            self._sorted(self.cvds, cvds),
            maxlen=self.cvds.maxlen
        )
