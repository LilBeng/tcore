from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(slots=True)
class OpenInterest:
    timestamp: datetime  # Close timestamp
    open_interest: Decimal
    single_open_interest: Decimal

    @classmethod
    def from_api(cls, data: dict) -> "OpenInterest":
        return cls(
            timestamp=datetime.fromtimestamp(int(data["timestamp"]) / 1000, timezone.utc),
            open_interest=Decimal(str(data["openInterest"])),
            single_open_interest=Decimal(str(data["singleOpenInterest"]))
        )
