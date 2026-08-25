import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from pybit.unified_trading import WebSocket, HTTP

from tcore.models.coin import Coin
from tcore.models.cvd import CVD
from tcore.models.enums import MarketInterval, Category
from tcore.models.funding import FundingRate
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest
from tcore.models.state import PeriodState
from tcore.models.tick import Ticker
from tcore.service.database import DatabaseService
from tcore.service.loader import HistoryDataLoader
from tcore.utils.filters import CoinFilter

logger = logging.getLogger(__name__)


class MarketDataStream:
    def __init__(
        self,
        coin_filter: CoinFilter,
        db_service: DatabaseService,
        category: Category = Category.LINEAR,
        interval: MarketInterval = MarketInterval.M1,
        chunk_size: int = 50,
        max_len: int = 100_000,
        update_time: timedelta = timedelta(hours=1),
        test_net: bool = False
    ) -> None:
        assert chunk_size <= 50

        self.coin_filter = coin_filter
        self.db_service = db_service
        self.category = category
        self.interval = interval
        self.chunk_size = chunk_size
        self.max_len = max_len
        self.update_time = update_time
        self.test_net = test_net

        self._coins: dict[str, Coin] = {}
        self._actual_symbols: set = set()
        self._last_cvds: dict[str, Decimal] = {}

        self._session = HTTP(testnet=self.test_net)
        self._loader = HistoryDataLoader(self._session)

        self._ws_connections: dict[WebSocket, set[str]] = defaultdict(set)

        # State for every symbol.
        self._states: dict[str, PeriodState] = {}

        # All websocket callbacks put events into this queue.
        self._queue: asyncio.Queue[Optional[tuple[str, dict]]] = asyncio.Queue()

        # Async worker.
        self._worker_task: Optional[asyncio.Task] = None
        self._instruments_task: Optional[asyncio.Task] = None

        # Event loop used by pybit callbacks.
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._running = False

    def _get_or_create_state(self, symbol: str, timestamp: datetime) -> PeriodState:
        period_start = timestamp.replace(
            minute=timestamp.minute - (timestamp.minute % self.interval),
            second=0,
            microsecond=0
        )

        state = self._states.get(symbol)
        if state is None:
            state = PeriodState(period_start=period_start)
            self._states[symbol] = state

        return state

    def _close_period(self, symbol: str, timestamp: datetime) -> None:
        state = self._states.pop(symbol, None)
        if state is None:
            return None

        self._persist_period(symbol, state)

        self._states[symbol] = PeriodState(
            period_start=timestamp + timedelta(minutes=self.interval.value)
        )

    def _persist_period(self, symbol: str, state: PeriodState) -> None:
        self._last_cvds[symbol] += state.cvd_delta

        self._store_cvd(
            symbol,
            CVD(
                timestamp=state.period_start,
                value=self._last_cvds[symbol],
                delta=state.cvd_delta
            )
        )

        if state.ticker is not None:
            ticker = state.ticker

            self._store_open_interest(
                symbol,
                OpenInterest(
                    timestamp=state.period_start,
                    open_interest=ticker.open_interest,
                    single_open_interest=ticker.single_open_interest
                )
            )

            self._store_funding_rate(
                symbol,
                FundingRate(
                    timestamp=state.period_start,
                    rate=ticker.funding_rate
                )
            )

            if coin := self._coins.get(symbol):
                coin.update_ticker(ticker)

        logger.debug(f"[{symbol}] period={state.period_start} trades={state.trade_count}")

    def _store_kline(self, symbol: str, kline: Kline) -> None:
        self.db_service.writer.add(symbol, kline)

        if symbol in self._actual_symbols:
            if coin := self._coins.get(symbol):
                coin.add_kline(kline)

    def _store_cvd(self, symbol: str, cvd: CVD) -> None:
        self.db_service.writer.add(symbol, cvd)

        if symbol in self._actual_symbols:
            if coin := self._coins.get(symbol):
                coin.add_cvd(cvd)

    def _store_open_interest(self, symbol: str, open_interest: OpenInterest) -> None:
        self.db_service.writer.add(symbol, open_interest)

        if symbol in self._actual_symbols:
            if coin := self._coins.get(symbol):
                coin.add_open_interest(open_interest)

    def _store_funding_rate(self, symbol: str, funding_rate: FundingRate) -> None:
        self.db_service.writer.add(symbol, funding_rate)

        if symbol in self._actual_symbols:
            if coin := self._coins.get(symbol):
                coin.add_funding_rate(funding_rate)

    # EVENT QUEUE
    def _enqueue(self, event_type: str, msg: dict) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return None

        try:
            loop.call_soon_threadsafe(self._queue.put_nowait, (event_type, msg))
        except RuntimeError:
            # Event loop has already been stopped.
            pass

    async def _worker(self) -> None:
        logger.info("Market data worker started")

        while True:
            event = await self._queue.get()

            try:
                # None is our shutdown signal.
                if event is None:
                    return None

                event_type, msg = event

                if event_type == "trade":
                    self._process_trade(msg)

                elif event_type == "ticker":
                    self._process_ticker(msg)

                elif event_type == "kline":
                    self._process_kline(msg)

                else:
                    logger.warning(f"Unknown market event: {event_type}")

            except Exception as exception:
                logger.exception(f"Market event processing error: {exception}")

            finally:
                self._queue.task_done()

    async def _get_coins(self, symbols: Optional[list] = None) -> dict[str, Coin]:
        coins = {}

        if symbols:
            instruments, tickers = await asyncio.gather(
                asyncio.gather(*(self._loader.load_instruments(self.category, symbol) for symbol in symbols)),
                asyncio.gather(*(self._loader.load_tickers(self.category, symbol) for symbol in symbols))
            )

            instruments = [instrument for batch in instruments for instrument in batch]
            tickers = [ticker for batch in tickers for ticker in batch]

        else:
            instruments, tickers = await asyncio.gather(
                self._loader.load_instruments(self.category),
                self._loader.load_tickers(self.category)
            )

        instruments = {instrument.symbol: instrument for instrument in instruments}
        tickers = {ticker.symbol: ticker for ticker in tickers}

        for key, instrument in instruments.items():
            ticker = tickers.get(key)

            if ticker:
                coin = Coin(instrument, ticker)
                coin.set_max_len(self.max_len)

                coins[instrument.symbol] = coin

            else:
                logger.warning(f"No ticker (symbol={key}) to subscribe")

        return coins

    async def _instruments_updater(self, symbols: Optional[list] = None) -> None:
        logger.info("Instruments updater worker started")

        while self._running:
            try:
                logger.info(f"Next update instruments in {int(self.update_time.total_seconds())}s")

                await asyncio.sleep(self.update_time.total_seconds())

                logger.info("Update instruments ...")

                await self._update_instruments(symbols)

            except asyncio.CancelledError:
                raise

            except Exception as exception:
                logger.exception(f"Failed to update instruments: {exception}")

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
            self.add_symbol(symbol)

            logger.info(f"New instrument added: {symbol}")

        for symbol in current_coin_symbols - actual_coin_symbols:
            self.remove_symbol(symbol)

            self._coins.pop(symbol, None)
            self._states.pop(symbol, None)
            self._last_cvds.pop(symbol, None)

            logger.info(f"Instrument removed: {symbol}")

        # Проверка для записи в память
        current_actual_symbols = set(self._actual_symbols)
        actual_symbols = {symbol for symbol, coin in coins.items() if self.coin_filter.check_coin(coin)}

        for symbol in actual_symbols - current_actual_symbols:
            self._actual_symbols.add(symbol)

            coin = self._coins.get(symbol)
            if coin:
                await self.db_service.writer.flush(symbol)

                klines, open_interests, funding_rates, cvds = await asyncio.gather(
                    self.db_service.database.klines.get(symbol, self.max_len),
                    self.db_service.database.open_interests.get(symbol, self.max_len),
                    self.db_service.database.funding_rates.get(symbol, self.max_len),
                    self.db_service.database.cvds.get(symbol, self.max_len)
                )

                klines.extend(coin.klines)
                open_interests.extend(coin.open_interests)
                funding_rates.extend(coin.funding_rates)
                cvds.extend(coin.cvds)

                coin.klines = deque({item.timestamp: item for item in klines}.values(), self.max_len)
                coin.open_interests = deque({item.timestamp: item for item in open_interests}.values(), self.max_len)
                coin.funding_rates = deque({item.timestamp: item for item in funding_rates}.values(), self.max_len)
                coin.cvds = deque({item.timestamp: item for item in cvds}.values(), self.max_len)

        for symbol in current_actual_symbols - actual_symbols:
            self._actual_symbols.remove(symbol)

            # Удаление данных из памяти
            coin = self._coins.get(symbol)
            if coin:
                coin.clear()

        logger.info("All instruments updated")

        del coins

    # TRADE
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

            # Bybit:
            # Buy  -> positive CVD
            # Sell -> negative CVD
            if trade.get("S") == "Buy":
                state.cvd_delta += size
            else:
                state.cvd_delta -= size

            state.trade_count += 1

    # TICKER
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

        state.ticker = ticker

    # KLINE
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
            self._store_kline(symbol, kline)
            self._close_period(symbol, kline.timestamp)

    # BYBIT CALLBACKS
    def handle_trade(self, msg: dict) -> None:
        self._enqueue("trade", msg)

    def handle_ticker(self, msg: dict) -> None:
        self._enqueue("ticker", msg)

    def handle_kline(self, msg: dict) -> None:
        self._enqueue("kline", msg)

    # WEBSOCKET
    def _create_connection(self, symbols: list[str]) -> WebSocket:
        ws = WebSocket(
            testnet=self.test_net,
            channel_type=self.category.value
        )

        ws.subscribe(f"kline.{self.interval.value}.{{symbol}}", self.handle_kline, symbols)
        ws.subscribe("publicTrade.{symbol}", self.handle_trade, symbols)
        ws.subscribe("tickers.{symbol}", self.handle_ticker, symbols)

        return ws

    def add_symbol(self, symbol: str) -> None:
        if any(symbol in symbols for symbols in self._ws_connections.values()):
            return None

        for ws, symbols in self._ws_connections.items():
            if len(symbols) >= self.chunk_size:
                continue

            ws.subscribe("tickers.{symbol}", self.handle_ticker, [symbol])
            ws.subscribe("publicTrade.{symbol}", self.handle_trade, [symbol])
            ws.subscribe(f"kline.{self.interval.value}.{{symbol}}", self.handle_kline, [symbol])

            symbols.add(symbol)

            logger.info(f"Symbol added: {symbol}, socket_symbols={len(symbols)}")

            return None

        # Все существующие сокеты заполнены.
        ws = self._create_connection([symbol])
        self._ws_connections[ws] = {symbol}

        logger.info(f"New WebSocket created for {symbol}")

    def remove_symbol(self, symbol: str) -> None:
        ws = next((ws for ws, symbols in self._ws_connections.items() if symbol in symbols), None)
        if ws is None:
            return None

        symbols = self._ws_connections.get(ws)

        ws.unsubscribe(f"tickers.{symbol}")
        ws.unsubscribe(f"publicTrade.{symbol}")
        ws.unsubscribe(f"kline.{self.interval.value}.{symbol}")

        symbols.remove(symbol)

        logger.info(f"Symbol removed: {symbol}, socket_symbols={len(symbols)}")

        if not symbols:
            ws.exit()

            self._ws_connections.pop(ws, None)

            logger.info("Empty WebSocket closed")

    # START
    async def start(self, symbols: Optional[list] = None) -> None:
        if self._running:
            logger.warning("Market data stream already running")
            return None

        # Start database service.
        await self.db_service.start()

        self._coins = await self._get_coins(symbols)
        self._actual_symbols = {symbol for symbol, coin in self._coins.items() if self.coin_filter.check_coin(coin)}

        for symbol in self._coins.keys():
            last_cvd = await self.db_service.database.cvds.get_last(symbol)
            self._last_cvds[symbol] = last_cvd.value if last_cvd is not None else Decimal(0)

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
            f"interval={self.interval.value}m, "
            f"chunk={self.chunk_size}"
        )

        # Start worker BEFORE websocket connections.
        self._worker_task = asyncio.create_task(
            self._worker(),
            name="market-data-worker"
        )

        self._instruments_task = asyncio.create_task(
            self._instruments_updater(symbols),
            name="instruments-updater"
        )

        # Create websocket connections.
        for start in range(0, len(symbols_to_subscribe), self.chunk_size):
            chunk = symbols_to_subscribe[start:start + self.chunk_size]

            ws = self._create_connection(chunk)

            self._ws_connections[ws] = set(chunk)

            logger.info(f"WebSocket #{len(self._ws_connections)}: {len(chunk)} symbols")

        logger.info(f"Market stream started: {len(self._ws_connections)} WebSockets")

    # STOP
    async def stop(self) -> None:
        if not self._running:
            return None

        logger.info("Stopping market data stream...")

        self._running = False

        # Stop accepting new websocket events first.
        for ws in self._ws_connections:
            try:
                ws.exit()
            except Exception as exception:
                logger.exception(f"Error closing WebSocket: {exception}")

        self._ws_connections.clear()

        # Wait until all queued events are processed.
        await self._queue.join()

        # Stop worker.
        if self._worker_task is not None:
            await self._queue.put(None)
            await self._worker_task
            self._worker_task = None

        if self._instruments_task:
            self._instruments_task.cancel()

            try:
                await self._instruments_task
            except asyncio.CancelledError:
                pass

            self._instruments_task = None

        # Persist final periods.
        for symbol in list(self._states):
            state = self._states.pop(symbol)

            if state.cvd_delta or state.ticker is not None or state.trade_count:
                self._persist_period(symbol, state)

                logger.info(f"[{symbol}] Final period closed: {state.trade_count} trades")

        # Flush and stop database service.
        await self.db_service.stop()

        self._loop = None

        logger.info("Market data stream stopped")
