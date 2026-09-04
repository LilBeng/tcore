from abc import ABC, abstractmethod

from tcore.models.coin import Coin


class BaseStrategy(ABC):

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @abstractmethod
    def check(self, coin: Coin) -> bool:
        ...
