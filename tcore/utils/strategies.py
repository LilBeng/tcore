from abc import ABC, abstractmethod

from tcore.models.coin import Coin


class BaseStrategy(ABC):
    """Базовый класс"""

    @abstractmethod
    def check(self, coin: Coin) -> bool:
        ...
