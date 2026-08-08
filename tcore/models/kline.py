from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class Kline(BaseModel):
    """Свеча с биржи Bybit"""
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
        """
        Создание свечи из списка данных API.

        Args:
            data: Список [timestamp_ms, open, high, low, close, volume, turnover]
            symbol: Торговый символ

        Returns:
            Объект Kline
        """
        return cls(
            symbol=symbol,
            timestamp=datetime.fromtimestamp(int(data[0]) / 1000),
            open=Decimal(str(data[1])),
            high=Decimal(str(data[2])),
            low=Decimal(str(data[3])),
            close=Decimal(str(data[4])),
            volume=Decimal(str(data[5])),
            turnover=Decimal(str(data[6]))
        )

    @property
    def is_bullish(self) -> bool:
        """Бычья свеча (закрытие выше открытия)"""
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """Медвежья свеча (закрытие ниже открытия)"""
        return self.close < self.open

    @property
    def body(self) -> Decimal:
        """Размер тела свечи (абсолютное значение)"""
        return abs(self.close - self.open)

    @property
    def wick_upper(self) -> Decimal:
        """Размер верхней тени"""
        return self.high - max(self.open, self.close)

    @property
    def wick_lower(self) -> Decimal:
        """Размер нижней тени"""
        return min(self.open, self.close) - self.low

    @property
    def total_range(self) -> Decimal:
        """Полный диапазон свечи (high - low)"""
        return self.high - self.low
