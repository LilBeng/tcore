from tcore.database.models import FundingRateDB
from tcore.database.repositories.base import BaseRepository
from tcore.models.funding import FundingRate


class FundingRateRepository(BaseRepository[FundingRateDB, FundingRate]):
    model = FundingRateDB

    def _to_entity(self, model: FundingRateDB) -> FundingRate:
        return FundingRate(
            timestamp=model.timestamp,
            rate=model.rate
        )

    def _to_values(self, symbol: str, entity: FundingRate) -> dict:
        return {
            "symbol": symbol,
            "timestamp": entity.timestamp,
            "rate": entity.rate
        }
