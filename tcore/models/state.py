from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from tcore.models.tick import Ticker


@dataclass(slots=True)
class PeriodState:
    period_start: datetime
    cvd_delta: Decimal = Decimal(0)
    ticker: Optional[Ticker] = None
    trade_count: int = 0
