import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Any

from pybit.unified_trading import WebSocket, HTTP
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from tcore.models.coin import Coin
from tcore.models.config import EngineConfig
from tcore.models.cvd import CVD
from tcore.models.enums import OrderSide, EventType
from tcore.models.funding import FundingRate
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest
from tcore.models.state import PeriodState
from tcore.models.tick import Ticker
from tcore.service.database import MarketDataService
from tcore.service.loader import HistoryDataLoader
from tcore.utils.strategy import BaseStrategy
from tcore.utils.validator import CoinValidator

logger = logging.getLogger(__name__)


class TradingEngine(object):
    def __init__(self, config: EngineConfig, coin_validator: CoinValidator, strategies: list[BaseStrategy]) -> None:
        self._config = config
        self._coin_validator = coin_validator
        self._strategies = strategies

        self._coins: dict[str, Coin] = {}
        self._actual_symbols: set = set()
        self._last_cvds: dict[str, Decimal] = {}

        self._market_service = MarketDataService(
            url=self._config.url_datetime,
            max_records=self._config.max_records,
            buffer_size=self._config.buffer_size,
            flush_interval=self._config.flush_interval
        )

        self._session = HTTP(
            testnet=self._config.test_net
        )

        adapter = HTTPAdapter(
            pool_connections=self._config.pool_connections,
            pool_maxsize=self._config.pool_maxsize,
            max_retries=Retry(
                total=self._config.max_retries,
                backoff_factor=self._config.backoff_factor
            )
        )

        self._session.client.mount("://", adapter)

        self._loader = HistoryDataLoader(
            session=self._session
        )

        self._ws_connections: dict[WebSocket, set[str]] = defaultdict(set)

        self._states: dict[str, PeriodState] = {}

        # Queues
        self._market_queue: asyncio.Queue[Optional[tuple[EventType, dict]]] = asyncio.Queue()
        self._strategies_queue: asyncio.Queue[Optional[BaseStrategy]] = asyncio.Queue()

        # Workers
        self._market_data_task: Optional[asyncio.Task] = None
        self._strategy_executor_task: Optional[asyncio.Task] = None
        self._instruments_updater_task: Optional[asyncio.Task] = None

        # Event loop
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._running = False

    def _enqueue(self, queue: asyncio.Queue, *items: Any) -> None:
        if self._loop is None or self._loop.is_closed():
            return None

        if not items:
            return None

        payload = items[0] if len(items) == 1 else items

        try:
            self._loop.call_soon_threadsafe(queue.put_nowait, payload)
        except RuntimeError:
            pass

    def _get_or_create_state(self, symbol: str, timestamp: datetime) -> PeriodState:
        state = self._states.get(symbol)
        if state is None:
            period_start = timestamp.replace(
                minute=timestamp.minute - (timestamp.minute % self._config.interval),
                second=0,
                microsecond=0
            )
            state = PeriodState(period_start=period_start)
            self._states[symbol] = state

        return state

    def _close_period(self, symbol: str) -> None:
        state = self._states.pop(symbol, None)
        if state is None:
            return None

        if kline := state.last_kline:
            self._store_kline(symbol, kline)
        else:
            logger.warning(f"[{symbol}] period=({state.period_start}-not closed) trades={state.trade_count}")

        period_end = state.period_start + timedelta(minutes=self._config.interval.value)

        self._last_cvds[symbol] += state.cvd_delta

        self._store_cvd(
            symbol,
            CVD(
                timestamp=state.period_start,
                value=self._last_cvds[symbol],
                delta=state.cvd_delta
            )
        )

        if ticker := state.last_ticker:
            self._store_open_interest(
                symbol,
                OpenInterest(
                    timestamp=period_end,
                    open_interest=ticker.open_interest,
                    single_open_interest=ticker.single_open_interest
                )
            )

            self._store_funding_rate(
                symbol,
                FundingRate(
                    timestamp=period_end,
                    rate=ticker.funding_rate
                )
            )

            if coin := self._coins.get(symbol):
                coin.update_ticker(ticker)

        logger.debug(f"[{symbol}] period=({state.period_start}-{period_end}) trades={state.trade_count}")

        self._states[symbol] = PeriodState(
            period_start=period_end
        )

        for strategy in self._strategies:
            self._enqueue(self._strategies_queue, strategy)

    def _store_kline(self, symbol: str, kline: Kline) -> None:
        self._market_service.writer.add(symbol, kline)

        if symbol in self._actual_symbols:
            if coin := self._coins.get(symbol):
                coin.add_kline(kline)

    def _store_cvd(self, symbol: str, cvd: CVD) -> None:
        self._market_service.writer.add(symbol, cvd)

        if symbol in self._actual_symbols:
            if coin := self._coins.get(symbol):
                coin.add_cvd(cvd)

    def _store_open_interest(self, symbol: str, open_interest: OpenInterest) -> None:
        self._market_service.writer.add(symbol, open_interest)

        if symbol in self._actual_symbols:
            if coin := self._coins.get(symbol):
                coin.add_open_interest(open_interest)

    def _store_funding_rate(self, symbol: str, funding_rate: FundingRate) -> None:
        self._market_service.writer.add(symbol, funding_rate)

        if symbol in self._actual_symbols:
            if coin := self._coins.get(symbol):
                coin.add_funding_rate(funding_rate)

    async def _worker_market_data(self) -> None:
        logger.info("Market data worker started")

        while True:
            event = await self._market_queue.get()

            try:
                # None is our shutdown signal.
                if event is None:
                    return None

                event_type, msg = event

                if event_type == EventType.TRADE:
                    self._process_trade(msg)

                elif event_type == EventType.TICKER:
                    self._process_ticker(msg)

                elif event_type == EventType.KLINE:
                    self._process_kline(msg)

                else:
                    logger.warning(f"Unknown market event: {event_type}")

            except Exception as exception:
                logger.exception(f"Market event processing error: {exception}")

            finally:
                self._market_queue.task_done()

    async def _worker_instruments_updater(self, symbols: Optional[list] = None) -> None:
        logger.info("Instruments updater worker started")

        while self._running:
            try:
                logger.info(
                    f"Next update instruments in {int(self._config.instruments_update_timedelta.total_seconds())}s"
                )

                await asyncio.sleep(self._config.instruments_update_timedelta.total_seconds())

                logger.info("Update instruments ...")

                await self._update_instruments(symbols)

            except asyncio.CancelledError:
                raise

            except Exception as exception:
                logger.exception(f"Failed to update instruments: {exception}")

    async def _worker_strategy_executor(self) -> None:
        logger.info("Strategy executor worker started")

        while True:
            strategy = await self._strategies_queue.get()

            try:
                # None is our shutdown signal.
                if strategy is None:
                    return None

            except Exception as exception:
                logger.exception(f"Strategy event processing error: {exception}")

            finally:
                self._strategies_queue.task_done()

    async def _get_coins(self, symbols: Optional[list] = None) -> dict[str, Coin]:
        coins = {}

        if symbols:
            instruments, tickers = await asyncio.gather(
                asyncio.gather(*(self._loader.load_instruments(self._config.category, symbol) for symbol in symbols)),
                asyncio.gather(*(self._loader.load_tickers(self._config.category, symbol) for symbol in symbols))
            )

            instruments = [instrument for batch in instruments for instrument in batch]
            tickers = [ticker for batch in tickers for ticker in batch]

        else:
            instruments, tickers = await asyncio.gather(
                self._loader.load_instruments(self._config.category),
                self._loader.load_tickers(self._config.category)
            )

        instruments = {instrument.symbol: instrument for instrument in instruments}
        tickers = {ticker.symbol: ticker for ticker in tickers}

        for key, instrument in instruments.items():
            ticker = tickers.get(key)

            if ticker:
                coins[instrument.symbol] = Coin(instrument, ticker, max_len=self._config.max_list_len)
            else:
                logger.warning(f"No ticker (symbol={key}) to subscribe")

        return coins

    async def _update_instruments(self, symbols: Optional[list] = None) -> None:
        coins = await self._get_coins(symbols)

        # Обновление данных инструмента
        for key, coin in coins.items():
            if actual_coin := self._coins.get(key):
                actual_coin.update_instrument(coin.instrument)

        # Проверка для добавления/отмены подписки
        current_coin_symbols = set(self._coins.keys())
        actual_coin_symbols = set(coins.keys())

        for symbol in actual_coin_symbols - current_coin_symbols:
            self._coins[symbol] = coins[symbol]

            self.subscribe_symbol(symbol)

            logger.info(f"New instrument added: {symbol}")

        for symbol in current_coin_symbols - actual_coin_symbols:
            self.unsubscribe_symbol(symbol)

            self._coins.pop(symbol, None)
            self._states.pop(symbol, None)
            self._last_cvds.pop(symbol, None)

            if symbol in self._actual_symbols:
                self._actual_symbols.remove(symbol)

            logger.info(f"Instrument removed: {symbol}")

        # Проверка для записи в память
        current_actual_symbols = set(self._actual_symbols)
        actual_symbols = {symbol for symbol, coin in coins.items() if self._coin_validator.validate(coin)}

        for symbol in actual_symbols - current_actual_symbols:
            self._actual_symbols.add(symbol)

            await self._update_coin_history(symbol)

            coin = self._coins.get(symbol)
            if coin:
                await self._market_service.writer.flush(symbol)

                klines, open_interests, funding_rates, cvds = await asyncio.gather(
                    self._market_service.database.klines.get(symbol, self._config.max_list_len),
                    self._market_service.database.open_interests.get(symbol, self._config.max_list_len),
                    self._market_service.database.funding_rates.get(symbol, self._config.max_list_len),
                    self._market_service.database.cvds.get(symbol, self._config.max_list_len)
                )

                coin.extend_klines(klines)
                coin.extend_open_interests(open_interests)
                coin.extend_funding_rates(funding_rates)
                coin.extend_cvds(cvds)

        for symbol in current_actual_symbols - actual_symbols:
            if symbol in self._actual_symbols:
                self._actual_symbols.remove(symbol)

            # Удаление данных из памяти
            coin = self._coins.get(symbol)
            if coin:
                coin.clear()

        logger.info("All instruments updated")

        del coins

    async def _update_coin_history(self, symbol: str) -> None:
        coin = self._coins.get(symbol)

        if self._config.interval.oi_interval:
            klines, open_interests = await asyncio.gather(
                *[
                    self._loader.load_klines(
                        symbol,
                        self._config.interval.kline_interval,
                        self._config.klines_history_limit
                    ),
                    self._loader.load_open_interest(
                        symbol,
                        self._config.interval.oi_interval,
                        self._config.oi_history_limit
                    )
                ]
            )

            coin.extend_klines(klines)
            coin.extend_open_interests(open_interests)

        else:
            klines = await self._loader.load_klines(
                symbol,
                self._config.interval.kline_interval,
                self._config.klines_history_limit
            )

            coin.extend_klines(klines)

    def _create_connection(self, symbols: list[str]) -> WebSocket:
        ws = WebSocket(
            testnet=self._config.test_net,
            channel_type=self._config.category.value
        )

        ws.subscribe(f"kline.{self._config.interval.value}.{{symbol}}", self.handle_kline, symbols)
        ws.subscribe("publicTrade.{symbol}", self.handle_trade, symbols)
        ws.subscribe("tickers.{symbol}", self.handle_ticker, symbols)

        return ws

    def _process_trade(self, msg: dict) -> None:
        topic = msg.get("topic", "")
        symbol = topic.removeprefix("publicTrade.")

        if symbol not in self._coins:
            return None

        data = msg.get("data")
        if not data:
            return None

        for trade in data:
            timestamp = datetime.fromtimestamp(int(trade.get("T")) / 1000, timezone.utc)

            state = self._get_or_create_state(symbol, timestamp)

            size = Decimal(trade.get("v"))

            if trade.get("S") == OrderSide.BUY.value:
                state.cvd_delta += size
            else:
                state.cvd_delta -= size

            state.trade_count += 1

    def _process_ticker(self, msg: dict) -> None:
        topic = msg.get("topic", "")
        symbol = topic.removeprefix("tickers.")

        if symbol not in self._coins:
            return None

        data = msg.get("data")
        if not data:
            return None

        timestamp = datetime.fromtimestamp(int(msg.get("ts")) / 1000, timezone.utc)

        ticker = Ticker(
            timestamp=timestamp,
            **data
        )

        state = self._get_or_create_state(symbol, timestamp)

        state.last_ticker = ticker

    def _process_kline(self, msg: dict) -> None:
        topic = msg.get("topic", "")

        parts = topic.split(".")
        if len(parts) < 3:
            return None

        symbol = parts[-1]

        if symbol not in self._coins:
            return None

        data_list = msg.get("data")
        if not data_list:
            return None

        data = data_list[0]

        kline = Kline(
            timestamp=datetime.fromtimestamp(int(data.get("start")) / 1000, timezone.utc),
            open=Decimal(data.get("open")),
            high=Decimal(data.get("high")),
            low=Decimal(data.get("low")),
            close=Decimal(data.get("close")),
            volume=Decimal(data.get("volume")),
            turnover=Decimal(data.get("turnover"))
        )

        if data.get("confirm"):
            state = self._get_or_create_state(symbol, kline.timestamp)
            if state:
                state.last_kline = kline

            self._close_period(symbol)

    def handle_trade(self, msg: dict) -> None:
        self._enqueue(self._market_queue, EventType.TRADE, msg)

    def handle_ticker(self, msg: dict) -> None:
        self._enqueue(self._market_queue, EventType.TICKER, msg)

    def handle_kline(self, msg: dict) -> None:
        self._enqueue(self._market_queue, EventType.KLINE, msg)

    def subscribe_symbol(self, symbol: str) -> None:
        if any(symbol in symbols for symbols in self._ws_connections.values()):
            return None

        for ws, symbols in self._ws_connections.items():
            if len(symbols) >= self._config.max_subscribe_size:
                continue

            ws.subscribe("tickers.{symbol}", self.handle_ticker, [symbol])
            ws.subscribe("publicTrade.{symbol}", self.handle_trade, [symbol])
            ws.subscribe(f"kline.{self._config.interval.value}.{{symbol}}", self.handle_kline, [symbol])

            symbols.add(symbol)

            logger.info(f"Symbol added: {symbol}, socket_symbols={len(symbols)}")

            return None

        # Все существующие сокеты заполнены.
        ws = self._create_connection([symbol])
        self._ws_connections[ws] = {symbol}

        logger.info(f"New WebSocket created for {symbol}")

    def unsubscribe_symbol(self, symbol: str) -> None:
        ws = next((ws for ws, symbols in self._ws_connections.items() if symbol in symbols), None)
        if ws is None:
            return None

        symbols = self._ws_connections.get(ws)

        ws.unsubscribe(f"tickers.{symbol}")
        ws.unsubscribe(f"publicTrade.{symbol}")
        ws.unsubscribe(f"kline.{self._config.interval.value}.{symbol}")

        symbols.remove(symbol)

        logger.info(f"Symbol removed: {symbol}, socket_symbols={len(symbols)}")

        if not symbols:
            ws.exit()

            self._ws_connections.pop(ws, None)

            logger.info("Empty WebSocket closed")

    async def start(self, symbols: Optional[list] = None) -> None:
        if self._running:
            logger.warning("Market data stream already running")
            return None

        await self._market_service.start()

        self._coins = await self._get_coins(symbols)
        self._actual_symbols = {symbol for symbol, coin in self._coins.items() if self._coin_validator.validate(coin)}

        for symbol in self._coins.keys():
            self._last_cvds[symbol] = Decimal(0)

        symbols_to_subscribe = list(self._coins)
        if not symbols_to_subscribe:
            logger.warning("No symbols to subscribe")
            return None

        self._loop = asyncio.get_running_loop()
        self._running = True

        logger.info(
            f"Starting market stream: "
            f"{len(symbols_to_subscribe)} symbols, "
            f"{len(self._actual_symbols)} actual symbols, "
            f"interval={self._config.interval.value}m, "
            f"chunk={self._config.max_subscribe_size}"
        )

        self._market_data_task = asyncio.create_task(
            self._worker_market_data(),
            name="market-data-worker"
        )

        self._strategy_executor_task = asyncio.create_task(
            self._worker_strategy_executor(),
            name="strategy-executor-worker"
        )

        self._instruments_updater_task = asyncio.create_task(
            self._worker_instruments_updater(symbols),
            name="instruments-updater-worker"
        )

        for start in range(0, len(symbols_to_subscribe), self._config.max_subscribe_size):
            chunk = symbols_to_subscribe[start:start + self._config.max_subscribe_size]

            logger.info(f"Downloads coins history data #{len(self._ws_connections) + 1}...")

            await asyncio.gather(
                *[self._update_coin_history(symbol) for symbol in chunk if symbol in self._actual_symbols]
            )

            ws = self._create_connection(chunk)

            self._ws_connections[ws] = set(chunk)

            logger.info(f"WebSocket #{len(self._ws_connections)}: {len(chunk)} symbols")

        logger.info(f"Market stream started: {len(self._ws_connections)} WebSockets")

    async def stop(self) -> None:
        if not self._running:
            return None

        logger.info("Stopping market data stream...")

        self._running = False

        for ws in self._ws_connections:
            try:
                ws.exit()
            except Exception as exception:
                logger.exception(f"Error closing WebSocket: {exception}")

        self._ws_connections.clear()

        await self._market_queue.join()

        if self._market_data_task:
            await self._market_queue.put(None)
            await self._market_data_task
            self._market_data_task = None

        await self._strategies_queue.join()

        if self._strategy_executor_task is not None:
            await self._strategies_queue.put(None)
            await self._strategy_executor_task
            self._strategy_executor_task = None

        if self._instruments_updater_task:
            self._instruments_updater_task.cancel()

            try:
                await self._instruments_updater_task
            except asyncio.CancelledError:
                pass

            self._instruments_updater_task = None

        self._states.clear()

        await self._market_service.stop()

        self._loop = None

        logger.info("Market data stream stopped")
