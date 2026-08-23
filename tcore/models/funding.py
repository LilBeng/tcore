from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(slots=True)
class FundingRate:
    timestamp: datetime
    rate: Decimal

    @classmethod
    def from_api(cls, data: dict) -> "FundingRate":
        return cls(
            timestamp=datetime.fromtimestamp(int(data["fundingRateTimestamp"]) / 1000, timezone.utc),
            rate=Decimal(data["fundingRate"])
        )
