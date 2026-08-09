from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CVD(BaseModel):
    """Cumulative Volume Delta (кумулятивная дельта объёма)."""
    model_config = ConfigDict(populate_by_name=True)

    symbol: str  # Торговый символ
    timestamp: datetime  # Время закрытия периода (например, конец 4-часовой свечи)
    value: Decimal  # Накопленное значение CVD с начала сессии
    delta: Decimal  # Дельта за текущий период (сумма покупок - сумма продаж)

    @property
    def is_bullish(self) -> bool:
        """Положительная дельта — покупатели агрессивнее"""
        return self.delta > 0

    @property
    def is_bearish(self) -> bool:
        """Отрицательная дельта — продавцы агрессивнее"""
        return self.delta < 0
