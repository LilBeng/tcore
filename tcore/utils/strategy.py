from abc import ABC, abstractmethod

from tcore.models.coin import Coin, CoinSnapshot


class BaseStrategy(ABC):

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @abstractmethod
    def execute(self, snapshot: CoinSnapshot) -> bool:
        ...
