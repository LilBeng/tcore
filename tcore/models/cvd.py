from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class CVD:
    timestamp: datetime
    value: Decimal
