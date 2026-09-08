from dataclasses import dataclass
from decimal import Decimal

from tcore.models.enums import InstrumentStatus


@dataclass(slots=True)
class LeverageFilter:
    min_leverage: Decimal
    max_leverage: Decimal
    leverage_step: Decimal


@dataclass(slots=True)
class LotSizeFilter:
    min_qty: Decimal
    max_qty: Decimal
    qty_step: Decimal


@dataclass(slots=True)
class PriceFilter:
    min_price: Decimal
    max_price: Decimal
    tick_size: Decimal


@dataclass(slots=True)
class RiskParameters:
    ratio_x: Decimal
    ratio_y: Decimal


@dataclass(slots=True)
class Instrument:
    symbol: str
    status: InstrumentStatus
    base_coin: str
    quote_coin: str
    leverage_filter: LeverageFilter
    lot_size_filter: LotSizeFilter
    price_filter: PriceFilter
    funding_interval: int
    upper_funding_rate: Decimal
    lower_funding_rate: Decimal
    risk_parameters: RiskParameters

    @classmethod
    def from_api(cls, data: dict) -> "Instrument":
        return cls(
            symbol=data["symbol"],
            status=InstrumentStatus(data["status"]),
            base_coin=data["baseCoin"],
            quote_coin=data["quoteCoin"],
            leverage_filter=LeverageFilter(
                min_leverage=Decimal(data["leverageFilter"]["minLeverage"]),
                max_leverage=Decimal(data["leverageFilter"]["maxLeverage"]),
                leverage_step=Decimal(data["leverageFilter"]["leverageStep"])
            ),
            lot_size_filter=LotSizeFilter(
                min_qty=Decimal(data["lotSizeFilter"]["minOrderQty"]),
                max_qty=Decimal(data["lotSizeFilter"]["maxOrderQty"]),
                qty_step=Decimal(data["lotSizeFilter"]["qtyStep"])
            ),
            price_filter=PriceFilter(
                min_price=Decimal(data["priceFilter"]["minPrice"]),
                max_price=Decimal(data["priceFilter"]["maxPrice"]),
                tick_size=Decimal(data["priceFilter"]["tickSize"])
            ),
            funding_interval=int(data.get("fundingInterval", 480)),
            upper_funding_rate=Decimal(data["upperFundingRate"]),
            lower_funding_rate=Decimal(data["lowerFundingRate"]),
            risk_parameters=RiskParameters(
                ratio_x=Decimal(data["riskParameters"]["priceLimitRatioX"]),
                ratio_y=Decimal(data["riskParameters"]["priceLimitRatioY"])
            )
        )
