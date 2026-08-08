from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Ticker(BaseModel):
    """Тик (рыночные данные) инструмента"""
    model_config = ConfigDict(populate_by_name=True)

    timestamp: datetime = Field(default_factory=datetime.now)
    symbol: str = Field(alias="symbol")

    # Ценовые поля
    last_price: Decimal = Field(alias="lastPrice")
    index_price: Decimal = Field(alias="indexPrice")
    mark_price: Decimal = Field(alias="markPrice")
    prev_price_24h: Decimal = Field(alias="prevPrice24h")
    price_24h_pcnt: Decimal = Field(alias="price24hPcnt")
    high_price_24h: Decimal = Field(alias="highPrice24h")
    low_price_24h: Decimal = Field(alias="lowPrice24h")
    prev_price_1h: Decimal = Field(alias="prevPrice1h")

    # Объёмы и обороты
    volume_24h: Decimal = Field(alias="volume24h")
    turnover_24h: Decimal = Field(alias="turnover24h")

    # Открытый интерес
    open_interest: Decimal = Field(alias="openInterest")
    open_interest_value: Decimal = Field(alias="openInterestValue")

    # Ставка финансирования
    funding_rate: Decimal = Field(alias="fundingRate")

    @property
    def price_change_24h(self) -> Decimal:
        """Абсолютное изменение цены за 24 часа"""
        return self.last_price - self.prev_price_24h

    @property
    def price_change_percent(self) -> Decimal:
        """Изменение цены в процентах за 24 часа"""
        return self.price_24h_pcnt * 100

    @property
    def is_funding_positive(self) -> bool:
        """Проверка положительной ставки финансирования"""
        return self.funding_rate > 0

    @property
    def spread_mark_to_index(self) -> Decimal:
        """Спред между маркировочной и индексной ценой"""
        return self.mark_price - self.index_price
