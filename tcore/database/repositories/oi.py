from tcore.database.models import OpenInterestDB
from tcore.database.repositories.base import BaseRepository
from tcore.models.oi import OpenInterest


class OpenInterestRepository(BaseRepository[OpenInterestDB, OpenInterest]):
    model = OpenInterestDB

    def _to_entity(self, model: OpenInterestDB) -> OpenInterest:
        return OpenInterest(
            timestamp=model.timestamp,
            open_interest=model.open_interest,
            single_open_interest=model.single_open_interest
        )

    def _to_values(self, symbol: str, entity: OpenInterest) -> dict:
        return {
            "symbol": symbol,
            "timestamp": entity.timestamp,
            "open_interest": entity.open_interest,
            "single_open_interest": entity.single_open_interest
        }
