from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, case

from tcore.database.models import OpenInterestDB
from tcore.database.repositories.base import BaseRepository
from tcore.models.enums import MarketInterval
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

    async def get_periods(
            self,
            symbol: str,
            interval: MarketInterval,
            limit: Optional[int] = None
    ) -> list[OpenInterest]:
        period = self._get_period(interval).label("period")

        last = func.row_number().over(
            partition_by=period,
            order_by=self.model.timestamp.desc()
        ).label("last")

        subquery = (
            select(
                self.model.timestamp,
                self.model.open_interest,
                self.model.single_open_interest,
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
                        (subquery.c.last == 1, subquery.c.open_interest)
                    )
                ).label("open_interest"),
                func.max(
                    case(
                        (
                            subquery.c.last == 1,
                            subquery.c.single_open_interest
                        )
                    )
                ).label("single_open_interest")
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
            OpenInterest(
                timestamp=datetime.fromtimestamp(
                    row.period / 1000,
                    timezone.utc
                ),
                open_interest=row.open_interest,
                single_open_interest=row.single_open_interest
            )
            for row in rows
        ]
