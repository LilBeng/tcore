import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from pybit.unified_trading import WebSocket, HTTP

from tcore.models.coin import Coin
from tcore.models.cvd import CVD
from tcore.models.funding import FundingRate
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest
from tcore.models.state import PeriodState
from tcore.models.tick import Ticker
from tcore.service.loader import HistoryDataLoader
from tcore.utils.filters import CoinFilter

logger = logging.getLogger(__name__)


class MarketDataStream:
    def __init__(
        self,
        interval: int,
        coin_filter: CoinFilter,
        chunk_size: int = 50,
        max_len: int = 100_000,
        test_net: bool = False
    ) -> None:
        assert chunk_size <= 50

        self.coins: dict[str, Coin] = {}
        self.interval = interval
        self.coin_filter = coin_filter
        self.chunk_size = chunk_size
        self.max_len = max_len
        self.test_net = test_net

        self.ws_connections: dict[WebSocket, set[str]] = defaultdict(set)

        # State for every symbol.
        self._states: dict[str, PeriodState] = {}

        # All websocket callbacks put events into this queue.
        self._queue: asyncio.Queue[Optional[tuple[str, dict]]] = asyncio.Queue()

        # Async worker.
        self._worker_task: Optional[asyncio.Task] = None

        # Event loop used by pybit callbacks.
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._running = False

    # PERIOD STATE
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

        if period_start > state.period_start:
            self._persist_period(symbol, state)

            state = PeriodState(period_start=period_start)
            self._states[symbol] = state

        return state

    def _persist_period(self, symbol: str, state: PeriodState) -> None:
        coin = self.coins.get(symbol)
        if coin is None:
            return None

        # CVD
        if state.trade_count >= 0:
            coin.add_cvd(
                CVD(
                    symbol=symbol,
                    timestamp=state.period_start,
                    value=coin.cvds[-1].value if coin.cvds else Decimal(0) + state.cvd_delta,
                    delta=state.cvd_delta
                )
            )

        # TICKER / OI / FUNDING
        if state.ticker is not None:
            ticker = state.ticker

            coin.update_ticker(ticker)

            coin.add_open_interest(
                OpenInterest(
                    symbol=symbol,
                    timestamp=state.period_start,
                    open_interest=ticker.open_interest,
                    single_open_interest=ticker.single_open_interest
                )
            )

            coin.add_funding_rate(
                FundingRate(
                    symbol=symbol,
                    fundingRateTimestamp=state.period_start,
                    fundingRate=ticker.funding_rate
                )
            )

        logger.debug(f"[{symbol}] period={state.period_start} trades={state.trade_count}")

    # EVENT QUEUE
    def _enqueue(self, event_type: str, msg: dict) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return None

        try:
            loop.call_soon_threadsafe(
                self._queue.put_nowait,
                (event_type, msg),
            )
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

    # TRADE
    def _process_trade(self, msg: dict) -> None:
        topic = msg.get("topic", "")

        symbol = topic.removeprefix("publicTrade.")
        if symbol not in self.coins:
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
        if symbol not in self.coins:
            return None

        data = msg.get("data")
        if not data:
            return None

        timestamp = datetime.fromtimestamp(int(msg.get("ts")) / 1000, timezone.utc)

        ticker = Ticker(timestamp=timestamp, **data)

        state = self._get_or_create_state(symbol, timestamp)
        state.ticker = ticker

    # KLINE
    def _process_kline(self, msg: dict) -> None:
        topic = msg.get("topic", "")

        parts = topic.split(".")
        if len(parts) < 3:
            return None

        symbol = parts[-1]

        coin = self.coins.get(symbol)
        if coin is None:
            return None

        data_list = msg.get("data")
        if not data_list:
            return None

        data = data_list[0]

        kline = Kline(
            symbol=symbol,
            timestamp=datetime.fromtimestamp(int(data.get("start")) / 1000, timezone.utc),
            open=Decimal(data.get("open")),
            high=Decimal(data.get("high")),
            low=Decimal(data.get("low")),
            close=Decimal(data.get("close")),
            volume=Decimal(data.get("volume")),
            turnover=Decimal(data.get("turnover"))
        )

        if data.get("confirm"):
            coin.add_kline(kline)

            # ----------------------------------------------------------
            # В будущем здесь будет отправление сигнала на проверку стратегии
            # ----------------------------------------------------------

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
            channel_type="linear"
        )

        ws.subscribe(f"kline.{self.interval}.{{symbol}}", self.handle_kline, symbols)
        ws.subscribe("publicTrade.{symbol}", self.handle_trade, symbols)
        ws.subscribe("tickers.{symbol}", self.handle_ticker, symbols)

        return ws

    def add_symbol(self, symbol: str) -> None:
        if any(symbol in symbols for symbols in self.ws_connections.values()):
            return None

        for ws, symbols in self.ws_connections.items():
            if len(symbols) < self.chunk_size:
                ws.subscribe("tickers.{symbol}", self.handle_ticker, [symbol])
                ws.subscribe("publicTrade.{symbol}", self.handle_trade, [symbol])
                ws.subscribe(f"kline.{self.interval}.{{symbol}}", self.handle_kline, [symbol])

                symbols.add(symbol)

                logger.info(f"Symbol added: {symbol}, socket_symbols={len(symbols)}")

                return None

            ws = self._create_connection([symbol])
            self.ws_connections[ws] = set(symbol)

            logger.info(f"New WebSocket created for {symbol}")

    def remove_symbol(self, symbol: str) -> None:
        for ws, symbols in self.ws_connections.items():
            if symbol not in symbols:
                continue

            ws.unsubscribe(f"tickers.{symbol}")
            ws.unsubscribe(f"publicTrade.{symbol}")
            ws.unsubscribe(f"kline.{self.interval}.{symbol}")

            symbols.remove(symbol)

            logger.info(f"Symbol removed: {symbol}, socket_symbols={len(symbols)}")

            if not symbols:
                ws.exit()

                del self.ws_connections[ws]

                logger.info("Empty WebSocket closed")

    # START
    async def start(self, coins: Optional[dict[str, Coin]] = None) -> None:
        if self._running:
            logger.warning("Market data stream already running")
            return None

        if coins:
            self.coins = coins
        else:
            session = HTTP(
                testnet=self.test_net
            )

            loader = HistoryDataLoader(session)

            instruments = {instrument.symbol: instrument for instrument in await loader.load_instruments()}
            tickers = {ticker.symbol: ticker for ticker in await loader.load_tickers()}

            for key, instrument in instruments.items():
                ticker = tickers.get(key)
                if ticker:
                    coin = Coin(instrument, ticker)
                    coin.set_max_len(self.max_len)

                    self.coins[instrument.symbol] = coin
                else:
                    logger.warning(f"No ticker (symbol={key}) to subscribe")

        symbols = list(self.coins)
        if not symbols:
            logger.warning("No symbols to subscribe")
            return None

        self._loop = asyncio.get_running_loop()
        self._running = True

        logger.info(
            f"Starting market stream: "
            f"{len(symbols)} symbols, "
            f"interval={self.interval}m, "
            f"chunk={self.chunk_size}"
        )

        # Start worker BEFORE websocket connections.
        self._worker_task = asyncio.create_task(
            self._worker(),
            name="market-data-worker"
        )

        # Create websocket connections.
        for start in range(0, len(symbols), self.chunk_size):
            chunk = symbols[start:start + self.chunk_size]

            ws = self._create_connection(chunk)

            self.ws_connections[ws] = set(chunk)

            logger.info(f"WebSocket #{len(self.ws_connections)}: {len(chunk)} symbols")

        logger.info(f"Market stream started: {len(self.ws_connections)} WebSockets")

    # STOP
    async def stop(self) -> None:
        if not self._running:
            return None

        logger.info("Stopping market data stream...")

        self._running = False

        # Stop accepting new websocket events first.
        for ws in self.ws_connections:
            try:
                ws.exit()
            except Exception as exception:
                logger.exception(f"Error closing WebSocket: {exception}")

        self.ws_connections.clear()

        # Wait until all queued events are processed.
        await self._queue.join()

        # Stop worker.
        if self._worker_task is not None:
            await self._queue.put(None)
            await self._worker_task
            self._worker_task = None

        # Persist final periods.
        for symbol in list(self._states):
            state = self._states.pop(symbol)

            if state.cvd_delta or state.ticker is not None or state.trade_count:
                self._persist_period(symbol, state)

                logger.info(f"[{symbol}] Final period closed: {state.trade_count} trades")

        self._loop = None

        logger.info("Market data stream stopped")
