from datetime import datetime, timezone
from decimal import Decimal

from pydantic import ConfigDict, Field, field_validator, BaseModel

from tcore.models.enums import OrderSide


class TradeHistory(BaseModel):
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

    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, value) -> datetime:
        if isinstance(value, (int, str)):
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        return value

    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        return self.side == OrderSide.SELL

    @property
    def volume_usdt(self) -> Decimal:
        return self.price * self.size
