from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class Kline(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str  # Торговый символ
    timestamp: datetime  # Время открытия свечи
    open: Decimal  # Цена открытия
    high: Decimal  # Максимальная цена
    low: Decimal  # Минимальная цена
    close: Decimal  # Цена закрытия
    volume: Decimal  # Объём торгов в базовой монете
    turnover: Decimal  # Оборот в котируемой монете

    @classmethod
    def from_api_list(cls, symbol: str, data: list) -> "Kline":
        return cls(
            symbol=symbol,
            timestamp=datetime.fromtimestamp(int(data[0]) / 1000, tz=timezone.utc),
            open=Decimal(str(data[1])),
            high=Decimal(str(data[2])),
            low=Decimal(str(data[3])),
            close=Decimal(str(data[4])),
            volume=Decimal(str(data[5])),
            turnover=Decimal(str(data[6]))
        )
