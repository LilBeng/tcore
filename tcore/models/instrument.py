from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from tcore.models.enums import InstrumentStatus


class LeverageFilter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    min_leverage: Decimal = Field(alias="minLeverage")
    max_leverage: Decimal = Field(alias="maxLeverage")
    leverage_step: Decimal = Field(alias="leverageStep")


class LotSizeFilter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    min_qty: Decimal = Field(alias="minOrderQty")
    max_qty: Decimal = Field(alias="maxOrderQty")
    qty_step: Decimal = Field(alias="qtyStep")


class PriceFilter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    min_price: Decimal = Field(alias="minPrice")
    max_price: Decimal = Field(alias="maxPrice")
    tick_size: Decimal = Field(alias="tickSize")


class RiskParameters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ratio_x: Decimal = Field(alias="priceLimitRatioX")  # <0.15 норма
    ratio_y: Decimal = Field(alias="priceLimitRatioY")  # <0.3 норма


class Instrument(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='ignore',
        frozen=False
    )

    symbol: str = Field(alias="symbol")  # Торговый символ
    status: InstrumentStatus  # Статус: Trading, Settling, Closed
    base_coin: str = Field(alias="baseCoin")  # Базовая монета
    quote_coin: str = Field(alias="quoteCoin")  # Котируемая монета
    leverage_filter: LeverageFilter = Field(alias="leverageFilter")  # Фильтр плеча (мин/макс)
    lot_size_filter: LotSizeFilter = Field(alias="lotSizeFilter")  # Фильтр размера лота
    price_filter: PriceFilter = Field(alias="priceFilter")  # Фильтр цены (мин/макс/шаг)
    funding_interval: int = Field(default=480, alias="fundingInterval")  # Интервал финансирования в минутах (480 = 8ч)
    upper_funding_rate: Decimal = Field(alias="upperFundingRate")  # Верхний лимит ставки финансирования
    lower_funding_rate: Decimal = Field(alias="lowerFundingRate")  # Нижний лимит ставки финансирования
    risk_parameters: RiskParameters = Field(alias="riskParameters")  # Параметры риска (лимиты цен)
