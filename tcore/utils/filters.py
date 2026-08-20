from dataclasses import dataclass

from tcore.models.coin import Coin


@dataclass(slots=True)
class CoinFilter(object):
    min_ratio_x: float = 0.15
    min_ratio_y: float = 0.3
    min_funding_rate: float = 1e-3
    min_volume_24h: float = 20_000_000

    def check_coin(self, coin: Coin) -> bool:
        if not coin.instrument.risk_parameters.ratio_x <= self.min_ratio_x:
            return False
        if not coin.instrument.risk_parameters.ratio_y <= self.min_ratio_y:
            return False
        if not coin.ticker.funding_rate <= self.min_funding_rate:
            return False
        if not coin.ticker.volume_24h <= self.min_volume_24h:
            return False

        return True

    def filter(self, coins: dict[str, Coin]) -> dict[str, Coin]:
        results = {}
        for name, coin in coins.items():
            if self.check_coin(coin):
                results[name] = coin
        return results
