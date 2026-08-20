from collections import deque
from typing import Union

from tcore.models.cvd import CVD
from tcore.models.funding import FundingRate
from tcore.models.instrument import Instrument
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest
from tcore.models.tick import Ticker


class Coin(object):
    def __init__(
            self,
            instrument: Instrument,
            ticker: Ticker,
            klines: list[Kline],
            open_interests: list[OpenInterest],
            funding_rates: list[FundingRate],
            cvds: list[CVD],
            max_len: int = 100_000
    ) -> None:
        self.instrument = instrument
        self.ticker = ticker
        self.klines = deque(klines, max_len)
        self.open_interests = deque(open_interests, max_len)
        self.funding_rates = deque(funding_rates, max_len)
        self.cvds = deque(cvds, max_len)

    @staticmethod
    def _add(queue: deque, obj: Union[Ticker, Kline, FundingRate, OpenInterest, CVD]) -> None:
        if queue and queue[-1].timestamp == obj.timestamp:
            queue[-1] = obj
        else:
            queue.append(obj)

    def update_instrument_data(self, instrument: Instrument) -> None:
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
