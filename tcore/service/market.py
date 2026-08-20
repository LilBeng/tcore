import logging
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pybit.unified_trading import WebSocket

from tcore.models.coin import Coin
from tcore.models.cvd import CVD
from tcore.models.funding import FundingRate
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest
from tcore.models.state import PeriodState
from tcore.models.tick import Ticker


logger = logging.getLogger(__name__)


class MarketDataStream:
    """
    High-performance Bybit market data stream.

    Sources:
        - publicTrade -> CVD
        - tickers     -> OI + Funding
        - kline       -> Kline

    TradeHistory objects are NOT created.
    CVD is calculated directly from trade messages.
    """
    def __init__(
        self,
        coins: dict[str, Coin],
        interval: int,
        chunk_size: int = 50,
        test_net: bool = False
    ) -> None:
        self.coins = coins
        self.interval = interval
        self.chunk_size = chunk_size
        self.test_net = test_net

        self.ws_connections: list[WebSocket] = []

        # State for every symbol.
        self._states: dict[str, PeriodState] = {}

        # Separate lock per symbol.
        # One active symbol doesn't block another symbol.
        self._locks: dict[str, threading.Lock] = {symbol: threading.Lock() for symbol in coins}

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
            return

        period_end = state.period_start + timedelta(minutes=self.interval)

        # CVD
        if state.cvd_delta:
            last_cvd = coin.cvds[-1].value if coin.cvds else Decimal(0)

            coin.add_cvd(
                CVD(
                    symbol=symbol,
                    timestamp=period_end,
                    value=last_cvd + state.cvd_delta,
                    delta=state.cvd_delta,
                )
            )

        # TICKER / OI / FUNDING
        if state.ticker is not None:
            ticker = state.ticker

            coin.update_ticker(ticker)

            coin.add_open_interest(
                OpenInterest(
                    symbol=symbol,
                    timestamp=period_end,
                    open_interest=ticker.open_interest,
                    single_open_interest=ticker.single_open_interest,
                )
            )

            coin.add_funding_rate(
                FundingRate(
                    symbol=symbol,
                    fundingRateTimestamp=period_end,
                    fundingRate=ticker.funding_rate,
                )
            )

        logger.debug(f"[{symbol}] period={state.period_start} trades={state.trade_count}")

    # TRADE -> CVD
    def handle_trade(self, msg: dict) -> None:
        """
        Process Bybit publicTrade.

        We don't create TradeHistory.
        Only CVD delta is calculated.
        """
        try:
            topic = msg.get("topic", "")
            symbol = topic.removeprefix("publicTrade.")
            if symbol not in self.coins:
                return None

            data = msg.get("data")
            if not data:
                return None

            # Bybit can theoretically send multiple trades
            # in one websocket message.
            with self._locks[symbol]:
                for trade in data:
                    timestamp = datetime.fromtimestamp(int(trade.get("T")) / 1000, timezone.utc)
                    state = self._get_or_create_state(symbol, timestamp)
                    size = Decimal(trade.get("v"))

                    # Bybit:
                    # S == Buy  -> positive CVD
                    # S == Sell -> negative CVD
                    if trade.get("S") == "Buy":
                        state.cvd_delta += size
                    else:
                        state.cvd_delta -= size

                    state.trade_count += 1

        except Exception as exception:
            logger.exception(f"Trade handler error: {exception}")

    # TICKER
    def handle_ticker(self, msg: dict) -> None:
        """
        Process ticker updates.

        Last ticker received inside the period is used.
        """
        try:
            topic = msg.get("topic", "")
            symbol = topic.removeprefix("tickers.")
            if symbol not in self.coins:
                return None

            data = msg.get("data")
            if not data:
                return None

            timestamp = datetime.fromtimestamp(int(msg.get("ts")) / 1000, timezone.utc)

            ticker = Ticker(timestamp=timestamp, **data)

            with self._locks[symbol]:
                state = self._get_or_create_state(symbol, timestamp)
                state.ticker = ticker

        except Exception as exception:
            logger.exception(f"Ticker handler error: {exception}")

    # KLINE
    def handle_kline(self, msg: dict) -> None:
        """
        Process kline updates.

        Unconfirmed candle:
            replace last candle

        Confirmed candle:
            add new candle
        """
        try:
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

            start = datetime.fromtimestamp(int(data.get("start")) / 1000, timezone.utc)
            end = datetime.fromtimestamp(int(data.get("end")) / 1000, timezone.utc)

            kline = Kline(
                symbol=symbol,
                timestamp=start + timedelta(minutes=1),
                open=Decimal(data.get("open")),
                high=Decimal(data.get("high")),
                low=Decimal(data.get("low")),
                close=Decimal(data.get("close")),
                volume=Decimal(data.get("volume")),
                turnover=Decimal(data.get("turnover"))
            )

            with self._locks[symbol]:
                if data.get("confirm") or end < datetime.now(timezone.utc):
                    coin.add_kline(kline)

                elif coin.klines:
                    last = coin.klines[-1]

                    if last.timestamp == kline.timestamp:
                        coin.klines[-1] = kline
                    elif kline.timestamp > last.timestamp:
                        coin.add_kline(kline)

        except Exception as exception:
            logger.exception(f"Kline handler error: {exception}")

    # WEBSOCKET
    def _create_connection(self, symbols: list[str]) -> WebSocket:
        ws = WebSocket(testnet=self.test_net, channel_type="linear")

        # One subscription request for ALL klines
        ws.subscribe(f"kline.{self.interval}." + "{symbol}", self.handle_kline, symbols)
        # One subscription request for ALL trades
        ws.subscribe("publicTrade.{symbol}", self.handle_trade, symbols)
        # One subscription request for ALL tickers
        ws.subscribe("tickers.{symbol}", self.handle_ticker, symbols)

        return ws

    def start(self) -> None:
        """
        Start websocket streams.

        Symbols are split between several WebSocket connections.
        """
        symbols = list(self.coins)
        if not symbols:
            logger.warning("No symbols to subscribe")
            return None

        logger.info(
            f"Starting market stream: {len(symbols)} symbols, "
            f"interval={self.interval}m, chunk={self.chunk_size}"
        )

        for start in range(0, len(symbols), self.chunk_size,):
            chunk = symbols[start:start + self.chunk_size]

            ws = self._create_connection(chunk)
            self.ws_connections.append(ws)

            logger.info(f"WebSocket #{len(self.ws_connections)}: {len(chunk)} symbols")

        logger.info(f"Market stream started: {len(self.ws_connections)} WebSockets")

    def stop(self) -> None:
        """
        Close websocket connections.
        """
        for symbol, lock in self._locks.items():
            with lock:
                state = self._states.pop(symbol, None)
                if state is None:
                    continue
                if state.cvd_delta or state.ticker is not None or state.trade_count:
                    self._persist_period(symbol, state)

                    logger.info(f"[{symbol}] Final period closed: {state.trade_count} trades")

        for ws in self.ws_connections:
            try:
                ws.exit()
            except Exception as exception:
                logger.exception(f"Error closing WebSocket: {exception}")

        self.ws_connections.clear()

        logger.info("Market data stream stopped")
