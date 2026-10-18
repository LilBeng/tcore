from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(slots=True)
class Kline:
    timestamp: datetime  # Open timestamp
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    turnover: Decimal

    @classmethod
    def from_api(cls, data: list) -> "Kline":
        return cls(
            timestamp=datetime.fromtimestamp(int(data[0]) / 1000, timezone.utc),
            open=Decimal(str(data[1])),
            high=Decimal(str(data[2])),
            low=Decimal(str(data[3])),
            close=Decimal(str(data[4])),
            volume=Decimal(str(data[5])),
            turnover=Decimal(str(data[6]))
        )
