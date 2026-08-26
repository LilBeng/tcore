from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, case

from tcore.database.models import FundingRateDB
from tcore.database.repositories.base import BaseRepository
from tcore.models.enums import MarketInterval
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

    async def get_periods(
        self,
        symbol: str,
        interval: MarketInterval,
        limit: Optional[int] = None
    ) -> list[FundingRate]:
        period = self._get_period(interval).label("period")

        last = func.row_number().over(
            partition_by=period,
            order_by=self.model.timestamp.desc()
        ).label("last")

        subquery = (
            select(
                self.model.timestamp,
                self.model.rate,
                period,
                last
            )
            .where(self.model.symbol == symbol)
            .subquery()
        )

        statement = (
            select(
                subquery.c.period,
                func.max(
                    case(
                        (subquery.c.last == 1, subquery.c.rate)
                    )
                ).label("rate")
            )
            .group_by(subquery.c.period)
            .order_by(subquery.c.period.desc())
        )

        if limit is not None:
            statement = statement.limit(limit)

        async with self._session_factory() as session:
            result = await session.execute(statement)
            rows = result.all()

        rows.reverse() # noqa

        return [
            FundingRate(
                timestamp=datetime.fromtimestamp(
                    row.period / 1000,
                    timezone.utc
                ),
                rate=row.rate
            )
            for row in rows
        ]
