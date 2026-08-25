from collections import deque
from dataclasses import field, dataclass
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
        if queue and queue[-1].timestamp == obj.timestamp:
            queue[-1] = obj
        else:
            queue.append(obj)

    def update_instrument(self, instrument: Instrument) -> None:
        self.instrument = instrument

    def update_ticker(self, ticker: Ticker) -> None:
        self.ticker = ticker

    def add_kline(self, kline: Kline) -> None:
        self._add(self.klines, kline)

    def add_open_interest(self, open_interest: OpenInterest) -> None:
        self._add(self.open_interests, open_interest)

    def add_funding_rate(self, funding_rate: FundingRate) -> None:
        self._add(self.funding_rates, funding_rate)

    def add_cvd(self, cvd: CVD) -> None:
        self._add(self.cvds, cvd)
