from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(slots=True)
class Ticker:
    timestamp: datetime
    symbol: str

    last_price: Decimal
    index_price: Decimal
    mark_price: Decimal
    prev_price_24h: Decimal
    price_24h_pcnt: Decimal
    high_price_24h: Decimal
    low_price_24h: Decimal
    prev_price_1h: Decimal

    volume_24h: Decimal
    turnover_24h: Decimal

    open_interest: Decimal
    open_interest_value: Decimal
    single_open_interest: Decimal
    single_open_interest_value: Decimal

    funding_rate: Decimal

    @classmethod
    def from_api(cls, data: dict, timestamp: datetime = datetime.now(timezone.utc)) -> "Ticker":
        return cls(
            timestamp=timestamp,
            symbol=data["symbol"],
            last_price=Decimal(data["lastPrice"]),
            index_price=Decimal(data["indexPrice"]),
            mark_price=Decimal(data["markPrice"]),
            prev_price_24h=Decimal(data["prevPrice24h"]),
            price_24h_pcnt=Decimal(data["price24hPcnt"]),
            high_price_24h=Decimal(data["highPrice24h"]),
            low_price_24h=Decimal(data["lowPrice24h"]),
            prev_price_1h=Decimal(data["prevPrice1h"]),
            volume_24h=Decimal(data["volume24h"]),
            turnover_24h=Decimal(data["turnover24h"]),
            open_interest=Decimal(data["openInterest"]),
            open_interest_value=Decimal(data["openInterestValue"]),
            single_open_interest=Decimal(data["singleOpenInterest"]),
            single_open_interest_value=Decimal(data["singleOpenInterestValue"]),
            funding_rate=Decimal(data["fundingRate"] or "0")
        )
