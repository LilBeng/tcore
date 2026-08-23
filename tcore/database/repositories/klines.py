from tcore.database.models import KlineDB
from tcore.database.repositories.base import BaseRepository
from tcore.models.kline import Kline


class KlineRepository(BaseRepository[KlineDB, Kline]):
    model = KlineDB

    def _to_entity(self, model: KlineDB) -> Kline:
        return Kline(
            timestamp=model.timestamp,
            open=model.open,
            high=model.high,
            low=model.low,
            close=model.close,
            volume=model.volume,
            turnover=model.turnover
        )

    def _to_values(self, symbol: str, entity: Kline) -> dict:
        return {
            "symbol": symbol,
            "timestamp": entity.timestamp,
            "open": entity.open,
            "high": entity.high,
            "low": entity.low,
            "close": entity.close,
            "volume": entity.volume,
            "turnover": entity.turnover
        }
