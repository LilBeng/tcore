from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field, field_validator, BaseModel

from tcore.models.enums import OrderSide


class TradeHistory(BaseModel):
    """
    История сделки.
    """
    model_config = ConfigDict(populate_by_name=True)

    symbol: str  # Торговый символ
    exec_id: str = Field(alias="execId")  # ID сделки
    price: Decimal  # Цена сделки
    size: Decimal  # Объём сделки
    side: OrderSide  # Сторона сделки: Buy/Sell
    timestamp: datetime = Field(alias="time")  # Время сделки
    is_block_trade: bool = Field(alias="isBlockTrade")  # Признак блок-трейда
    is_rpi_trade: bool = Field(alias="isRPITrade")  # Признак RPI трейда
    seq: str  # Последовательность

    @classmethod
    @field_validator('timestamp', mode='before')
    def parse_timestamp(cls, value) -> datetime:
        """Парсинг timestamp из миллисекунд в datetime"""
        if isinstance(value, (int, str)):
            return datetime.fromtimestamp(int(value) / 1000)
        return value

    @property
    def is_buy(self) -> bool:
        """Проверка, что сделка на покупку"""
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        """Проверка, что сделка на продажу"""
        return self.side == OrderSide.SELL

    @property
    def volume_usdt(self) -> Decimal:
        """Объём сделки в USDT"""
        return self.price * self.size
