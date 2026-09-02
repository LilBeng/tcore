import operator
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Union

from tcore.models.coin import Coin


class Operator(Enum):
    LT = operator.lt
    LE = operator.le
    GT = operator.gt
    GE = operator.ge
    EQ = operator.eq
    NE = operator.ne


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
        return all(condition.check(value) for condition in self.conditions)


@dataclass(slots=True)
class CoinFilter(object):
    ratio_x: Validator = field(default_factory=Validator)
    ratio_y: Validator = field(default_factory=Validator)
    funding_rate: Validator = field(default_factory=Validator)
    volume_24h: Validator = field(default_factory=Validator)

    def validate(self, coin: Coin) -> bool:
        return all(
            [
                self.ratio_x.validate(coin.instrument.risk_parameters.ratio_x),
                self.ratio_y.validate(coin.instrument.risk_parameters.ratio_y),
                self.funding_rate.validate(coin.ticker.funding_rate),
                self.volume_24h.validate(coin.ticker.volume_24h)
            ]
        )
