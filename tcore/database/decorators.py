from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import String, BigInteger
from sqlalchemy.types import TypeDecorator


class DecimalType(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value: Optional[Decimal], dialect: Any) -> Optional[str]:
        return str(value) if value is not None else None

    def process_result_value(self, value: Optional[str], dialect: Any) -> Optional[Decimal]:
        return Decimal(value) if value is not None else None


class TimestampType(TypeDecorator):
    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect: Any) -> Optional[int]:
        if value is None:
            return None

        if value.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware")

        return int(value.astimezone(timezone.utc).timestamp() * 1000)

    def process_result_value(self, value: Optional[int], dialect: Any) -> Optional[datetime]:
        if value is None:
            return None

        return datetime.fromtimestamp(value / 1000, timezone.utc)
