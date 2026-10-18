from dataclasses import dataclass, field
from decimal import Decimal
from typing import Union

from tcore.models.coin import Coin
from tcore.utils.enums import Operator


@dataclass(slots=True)
class Condition:
    operator: Operator
    value: Union[int, float, Decimal]

    def check(self, other: Union[int, float, Decimal]) -> bool:
        return self.operator.value(other, self.value)


@dataclass(slots=True)
class Validator:
    conditions: list[Condition] = field(default_factory=list)

    def validate(self, value: Union[int, float, Decimal]) -> bool:
        if self.conditions:
            return all(condition.check(value) for condition in self.conditions)
        return True


@dataclass(slots=True)
class CoinValidator(object):
    ratio_x: Validator = field(default_factory=Validator)
    ratio_y: Validator = field(default_factory=Validator)
    funding_rate: Validator = field(default_factory=Validator)
    volume_24h: Validator = field(default_factory=Validator)
    turnover_24h: Validator = field(default_factory=Validator)

    def validate(self, coin: Coin) -> bool:
        return all(
            [
                self.ratio_x.validate(coin.instrument.risk_parameters.ratio_x),
                self.ratio_y.validate(coin.instrument.risk_parameters.ratio_y),
                self.funding_rate.validate(coin.ticker.funding_rate),
                self.volume_24h.validate(coin.ticker.volume_24h),
                self.volume_24h.validate(coin.ticker.turnover_24h)
            ]
        )
