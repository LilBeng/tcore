from tcore.database.models import CVDDB
from tcore.database.repositories.base import BaseRepository
from tcore.models.cvd import CVD


class CVDRepository(BaseRepository[CVDDB, CVD]):
    model = CVDDB

    def _to_entity(self, model: CVDDB) -> CVD:
        return CVD(
            timestamp=model.timestamp,
            value=model.value,
            delta=model.delta
        )

    def _to_values(self, symbol: str, entity: CVD) -> dict:
        return {
            "symbol": symbol,
            "timestamp": entity.timestamp,
            "value": entity.value,
            "delta": entity.delta
        }
