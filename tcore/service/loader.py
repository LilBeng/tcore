import asyncio
import logging
import time
from functools import partial
from typing import Optional

from pybit.unified_trading import HTTP

from tcore.models.enums import KlineInterval, Category, InstrumentStatus, OIInterval
from tcore.models.funding import FundingRate
from tcore.models.history import TradeHistory
from tcore.models.instrument import Instrument
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest
from tcore.models.tick import Ticker
from tcore.utils.decorators import singleton

logger = logging.getLogger(__name__)


@singleton
class HistoryDataLoader(object):
    """Асинхронный загрузчик исторических данных с ByBit"""

    def __init__(self, session: HTTP) -> None:
        self.session = session

    @staticmethod
    async def _fetch_with_retry(fetch_func, error_msg: str, max_retries: int = 3) -> dict:
        """Универсальный метод запроса с повторными попытками"""
        for attempt in range(max_retries + 1):
            try:
                resp = await asyncio.to_thread(fetch_func)
                if resp['retCode'] != 0:
                    raise ValueError(resp.get('retMsg', 'Unknown API error'))

                return resp

            except (ValueError, Exception) as e:
                if attempt == max_retries:
                    logger.error(f"{error_msg} after {max_retries} attempts: {e}")
                    raise

                delay = 2 ** attempt
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)

        return {}

    async def load_instruments(
            self,
            category: Category = Category.LINEAR,
            symbol: Optional[str] = None,
            status: InstrumentStatus = InstrumentStatus.TRADING,
            max_retries: int = 3
    ) -> list[Instrument]:
        """
        Загрузка инструментов с курсорной пагинацией.
        """
        instruments = []
        cursor = None

        while True:
            params = {
                "category": category.value,
                "status": status.value,
                "limit": 1000
            }
            if symbol:
                params["symbol"] = symbol
            if cursor:
                params["cursor"] = cursor

            resp = await self._fetch_with_retry(
                fetch_func=partial(self.session.get_instruments_info, **params),
                error_msg="Failed to load instruments",
                max_retries=max_retries
            )

            if not resp:
                break

            batch = [Instrument(**item) for item in resp['result']['list']]
            instruments.extend(batch)

            logger.info(
                f"Loaded batch of {len(batch)} instruments. "
                f"Total: {len(instruments)}"
            )

            cursor = resp['result'].get('nextPageCursor')
            if not cursor:
                logger.info(f"Loading completed. Total instruments: {len(instruments)}")
                break

            await asyncio.sleep(0.1)

        return instruments

    async def load_tickers(
            self,
            category: Category = Category.LINEAR,
            symbol: Optional[str] = None,
            max_retries: int = 3
    ) -> list[Ticker]:
        """
        Загрузка тиков (рыночных данных) [Обновление каждые 24 часа].
        """
        params = {"category": category.value}
        if symbol:
            params["symbol"] = symbol

        resp = await self._fetch_with_retry(
            fetch_func=partial(self.session.get_tickers, **params),
            error_msg="Failed to load ticks",
            max_retries=max_retries
        )

        if not resp:
            return []

        return [Ticker(**item) for item in resp['result']['list']]

    async def load_klines(
            self,
            symbol: str,
            interval: KlineInterval,
            limit: int = 1000,
            category: Category = Category.LINEAR,
            max_retries: int = 3
    ) -> list[Kline]:
        """
        Асинхронная загрузка исторических свечей.
        Пагинация через параметр end (timestamp самой старой свечи).
        """
        all_klines = []
        end = int(time.time() * 1000)

        while len(all_klines) < limit:
            batch_size = min(1000, limit - len(all_klines))

            params = {
                "category": category.value,
                "symbol": symbol,
                "interval": interval.value,
                "limit": batch_size,
                "end": end
            }

            resp = await self._fetch_with_retry(
                fetch_func=partial(self.session.get_kline, **params),
                error_msg=f"Failed to load klines for {symbol}",
                max_retries=max_retries
            )

            if not resp:
                break

            items = resp['result']['list']
            all_klines.extend(items)

            logger.info(
                f"Loaded {len(items)} klines for {symbol}. "
                f"Total: {len(all_klines)}/{limit}"
            )

            if len(items) < batch_size:
                # API вернул меньше чем просили — данные закончились
                break

            # Берём timestamp самой старой свечи для следующей страницы
            end = int(items[-1][0]) - 1

            await asyncio.sleep(0.1)

        # Сортировка от старых к новым
        all_klines.sort(key=lambda x: int(x[0]))

        # Обрезаем до лимита (если вдруг загрузили больше)
        all_klines = all_klines[-limit:]

        return [Kline.from_api_list(symbol, k) for k in all_klines]

    async def load_open_interest(
            self,
            symbol: str,
            interval: OIInterval,
            limit: int = 1000,
            category: Category = Category.LINEAR,
            max_retries: int = 3
    ) -> list[OpenInterest]:
        """
        Асинхронная загрузка истории открытого интереса.
        Пагинация через cursor.

        Args:
            symbol: Торговый символ
            interval: Интервал данных
            limit: Количество записей
            category: Категория
            max_retries: Максимальное количество повторных попыток

        Returns:
            Список записей открытого интереса, отсортированный от старых к новым
        """
        all_items = []
        cursor = None

        async def fetch_page(page_cursor: Optional[str], _page_limit: int) -> dict:
            """Загрузка одной страницы"""
            params = {
                "category": category.value,
                "symbol": symbol,
                "intervalTime": interval.value,
                "limit": _page_limit
            }
            if page_cursor:
                params["cursor"] = page_cursor

            return await self._fetch_with_retry(
                fetch_func=partial(self.session.get_open_interest, **params),
                error_msg=f"Failed to load OI for {symbol}",
                max_retries=max_retries
            )

        while len(all_items) < limit:
            remaining = limit - len(all_items)
            page_limit = min(200, remaining)

            resp = await fetch_page(cursor, page_limit)
            if not resp:
                break

            items = resp['result'].get('list', [])
            if not items:
                break
            all_items.extend(items)

            logger.info(
                f"Loaded {len(items)} OI records for {symbol}. "
                f"Total: {len(all_items)}/{limit}"
            )

            cursor = resp['result'].get('nextPageCursor')
            if not cursor or len(items) < page_limit:
                break

            await asyncio.sleep(0.1)

        # Берём последние limit записей и разворачиваем (старые → новые)
        selected_items = all_items[-limit:] if len(all_items) > limit else all_items

        result = [OpenInterest(symbol=symbol, **item) for item in reversed(selected_items)]

        logger.info(f"Loaded {len(result)} OI records for {symbol}")
        return result

    async def load_funding_rates(
            self,
            symbol: str,
            limit: int = 200,
            category: Category = Category.LINEAR,
            max_retries: int = 3
    ) -> list[FundingRate]:
        """
        Загрузка истории ставок финансирования.

        Args:
            symbol: Торговый символ
            limit: Количество записей (макс. 200)
            category: Категория
            max_retries: Максимальное количество повторных попыток

        Returns:
            Список ставок финансирования от старых к новым
        """
        params = {
            "category": category.value,
            "symbol": symbol,
            "limit": min(limit, 200)
        }

        resp = await self._fetch_with_retry(
            fetch_func=partial(self.session.get_funding_rate_history, **params),
            error_msg=f"Failed to load funding rate for {symbol}",
            max_retries=max_retries
        )

        if not resp:
            return []

        # API возвращает от новых к старым, разворачиваем
        items = resp['result']['list']
        result = [FundingRate(**item) for item in reversed(items)]

        logger.info(f"Loaded {len(result)} funding rates for {symbol}")
        return result

    async def load_trade_history(
            self,
            symbol: str,
            limit: int = 1000,
            category: Category = Category.LINEAR,
            max_retries: int = 3
    ) -> list[TradeHistory]:
        """
        Загрузка истории сделок.

        Args:
            symbol: Торговый символ
            limit: Количество сделок (макс. 1000)
            category: Категория
            max_retries: Максимальное количество повторных попыток

        Returns:
            Список сделок, отсортированный от старых к новым
        """
        params = {
            "category": category.value,
            "symbol": symbol,
            "limit": min(limit, 1000)
        }

        resp = await self._fetch_with_retry(
            fetch_func=partial(self.session.get_public_trade_history, **params),
            error_msg=f"Failed to load trades for {symbol}",
            max_retries=max_retries
        )

        if not resp:
            return []

        items = resp['result']['list'][:limit]

        # Сортировка от старых к новым
        sorted_items = sorted(items, key=lambda x: int(x.get('time', 0)))

        result = [TradeHistory(**item) for item in sorted_items]

        logger.info(f"Loaded {len(result)} trades for {symbol}")
        return result
