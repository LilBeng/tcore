from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Ticker(BaseModel):
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

    single_open_interest: Decimal = Field(alias="singleOpenInterest")
    single_open_interest_value: Decimal = Field(alias="singleOpenInterestValue")

    # Ставка финансирования
    funding_rate: Decimal = Field(alias="fundingRate")

    @model_validator(mode='before')
    @classmethod
    def handle_empty_strings(cls, values):
        if isinstance(values, dict) and values.get('fundingRate') == '':
            values['fundingRate'] = '0'
        return values
