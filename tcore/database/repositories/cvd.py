from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, case

from tcore.database.models import CVDDB
from tcore.database.repositories.base import BaseRepository
from tcore.models.cvd import CVD
from tcore.models.enums import MarketInterval


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

    async def get_periods(self, symbol: str, interval: MarketInterval, limit: Optional[int] = None) -> list[CVD]:
        period = self._get_period(interval).label("period")

        last = func.row_number().over(
            partition_by=period,
            order_by=self.model.timestamp.desc()
        ).label("last")

        subquery = (
            select(
                self.model.timestamp,
                self.model.value,
                self.model.delta,
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
                        (subquery.c.last == 1, subquery.c.value)
                    )
                ).label("value"),
                func.sum(subquery.c.delta).label("delta")
            )
            .group_by(subquery.c.period)
            .order_by(subquery.c.period.desc())
        )

        if limit is not None:
            statement = statement.limit(limit)

        async with self._session_factory() as session:
            result = await session.execute(statement)
            rows = result.all()

        rows.reverse()  # noqa

        return [
            CVD(
                timestamp=datetime.fromtimestamp(
                    row.period / 1000,
                    timezone.utc
                ),
                value=row.value,
                delta=row.delta
            )
            for row in rows
        ]
