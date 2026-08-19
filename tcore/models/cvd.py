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
