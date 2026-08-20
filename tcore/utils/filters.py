from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from tcore.models.instrument import Instrument, RiskParameters


class BaseFilter(ABC):
    """Базовый класс"""
    @abstractmethod
    def filter(self, *args) -> Any:
        ...


class InstrumentFilter(BaseFilter):
    """Фильтр для инструмента"""
    def __init__(
            self,
            min_risk_parameters: RiskParameters = RiskParameters(ratio_x=Decimal(0.15), ratio_y=Decimal(0.3))
    ) -> None:
        self.min_risk_parameters = min_risk_parameters

    def filter(self, instruments: list[Instrument]) -> list[Instrument]:
        """Фильтрация данных"""
        results = []
        for instrument in instruments:
            ratio_x = instrument.risk_parameters.ratio_x <= self.min_risk_parameters.ratio_x
            ratio_y = instrument.risk_parameters.ratio_y <= self.min_risk_parameters.ratio_y
            if ratio_x and ratio_y:
                results.append(instrument)
        return results
