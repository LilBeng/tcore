from abc import ABC, abstractmethod

from tcore.models.coin import Coin


class BaseStrategy(ABC):

    @abstractmethod
    def check(self, coin: Coin) -> bool:
        ...
