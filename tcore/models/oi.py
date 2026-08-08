from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from tcore.models.enums import Category


class OpenInterest(BaseModel):
    """
    Открытый интерес по инструменту.
    """
    model_config = ConfigDict(populate_by_name=True)

    symbol: str = Field(alias="symbol")  # Торговый символ
    timestamp: datetime  # Время данных
    oi_value: Decimal = Field(alias="openInterest")  # Общий открытый интерес
    single_oi_value: Decimal = Field(alias="singleOpenInterest")  # Открытый интерес в базовой монете

    @classmethod
    @field_validator('timestamp', mode='before')
    def parse_timestamp(cls, value) -> datetime:
        """Парсинг timestamp из миллисекунд в datetime"""
        if isinstance(value, str):
            return datetime.fromtimestamp(int(value) / 1000)
        return value
