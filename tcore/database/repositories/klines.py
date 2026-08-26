from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, case

from tcore.database.models import KlineDB
from tcore.database.repositories.base import BaseRepository
from tcore.models.enums import MarketInterval
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

    async def get_periods(self, symbol: str, interval: MarketInterval, limit: Optional[int] = None) -> list[Kline]:
        period = self._get_period(interval).label("period")

        first = func.row_number().over(
            partition_by=period,
            order_by=self.model.timestamp
        ).label("first")

        last = func.row_number().over(
            partition_by=period,
            order_by=self.model.timestamp.desc()
        ).label("last")

        subquery = (
            select(
                self.model.timestamp,
                self.model.open,
                self.model.high,
                self.model.low,
                self.model.close,
                self.model.volume,
                self.model.turnover,
                period,
                first,
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
                        (subquery.c.first == 1, subquery.c.open)
                    )
                ).label("open"),
                func.max(subquery.c.high).label("high"),
                func.min(subquery.c.low).label("low"),
                func.max(
                    case(
                        (subquery.c.last == 1, subquery.c.close)
                    )
                ).label("close"),
                func.sum(subquery.c.volume).label("volume"),
                func.sum(subquery.c.turnover).label("turnover")
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
            Kline(
                timestamp=datetime.fromtimestamp(
                    row.period / 1000,
                    timezone.utc
                ),
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
                turnover=row.turnover
            )
            for row in rows
        ]
