from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from tcore.models.kline import Kline
from tcore.models.tick import Ticker


@dataclass(slots=True)
class PeriodState:
    last_cvd_value: Decimal = Decimal(0)
    last_kline: Optional[Kline] = None
    last_ticker: Optional[Ticker] = None
    trade_count: int = 0

    def reset(self, reset_cvd: bool = False) -> None:
        if reset_cvd:
            self.last_cvd_value = Decimal(0)

        self.last_kline = None
        self.last_ticker = None
        self.trade_count = 0
