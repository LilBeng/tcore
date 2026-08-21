from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FundingRate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str = Field(alias="symbol")  # Торговый символ
    timestamp: datetime = Field(alias="fundingRateTimestamp")  # Время ставки
    rate: Decimal = Field(alias="fundingRate")  # Значение ставки

    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, value) -> datetime:
        if isinstance(value, str):
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        return value
