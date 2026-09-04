from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from tcore.models.kline import Kline
from tcore.models.tick import Ticker


@dataclass(slots=True)
class PeriodState:
    period_start: datetime
    last_kline: Optional[Kline] = None
    last_ticker: Optional[Ticker] = None
    cvd_delta: Decimal = Decimal(0)
    trade_count: int = 0
