import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from pybit.unified_trading import WebSocket

from tcore.base.coin import Coin
from tcore.models.cvd import CVD
from tcore.models.funding import FundingRate
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest
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

    @dataclass(slots=True)
    class PeriodState:
        period_start: datetime
        cvd_delta: Decimal = Decimal(0)
        ticker: Optional[Ticker] = None
        trade_count: int = 0

    def __init__(
        self,
        coins: dict[str, Coin],
        interval: int = 15,
        chunk_size: int = 50,
    ):
        self.coins = coins
        self.interval = interval
        self.chunk_size = chunk_size

        self.ws_connections: list[WebSocket] = []

        # State for every symbol.
        self._states: dict[str, MarketDataStream.PeriodState] = {}

        # Separate lock per symbol.
        # One active symbol doesn't block another symbol.
        self._locks: dict[str, threading.Lock] = {
            symbol: threading.Lock()
            for symbol in coins
        }

    # ------------------------------------------------------------------
    # PERIOD
    # ------------------------------------------------------------------

    def _get_period_start(self, timestamp: datetime) -> datetime:
        minute = timestamp.minute - (
            timestamp.minute % self.interval
        )

        return timestamp.replace(
            minute=minute,
            second=0,
            microsecond=0,
        )

    def _get_or_create_state(
        self,
        symbol: str,
        timestamp: datetime,
    ) -> PeriodState:
        period_start = self._get_period_start(timestamp)

        state = self._states.get(symbol)

        if state is None:
            state = self.PeriodState(
                period_start=period_start
            )
            self._states[symbol] = state

        if period_start > state.period_start:
            self._persist_period(symbol, state)

            state = self.PeriodState(
                period_start=period_start
            )
            self._states[symbol] = state

        return state

    def _persist_period(
        self,
        symbol: str,
        state: PeriodState,
    ) -> None:

        coin = self.coins.get(symbol)

        if coin is None:
            return

        period_end = (
            state.period_start
            + timedelta(minutes=self.interval)
        )

        # --------------------------------------------------------------
        # CVD
        # --------------------------------------------------------------

        if state.cvd_delta:
            last_cvd = (
                coin.cvds[-1].value
                if coin.cvds
                else Decimal(0)
            )

            cvd = CVD(
                symbol=symbol,
                timestamp=period_end,
                value=last_cvd + state.cvd_delta,
                delta=state.cvd_delta,
            )

            coin.add_cvd(cvd)

        # --------------------------------------------------------------
        # TICKER / OI / FUNDING
        # --------------------------------------------------------------

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

        logger.debug(
            "[%s] period=%s trades=%d cvd_delta=%s",
            symbol,
            state.period_start,
            state.trade_count,
            state.cvd_delta,
        )

        print(coin.klines)
        print(coin.open_interests)
        print(coin.funding_rates)
        print(coin.cvds)

    # ------------------------------------------------------------------
    # TRADE -> CVD
    # ------------------------------------------------------------------

    def handle_trade(self, msg: dict) -> None:
        """
        Process Bybit publicTrade.

        We don't create TradeHistory.
        Only CVD delta is calculated.
        """

        try:
            topic = msg.get("topic", "")

            # publicTrade.BTCUSDT
            symbol = topic.removeprefix("publicTrade.")

            if symbol not in self.coins:
                return

            data = msg.get("data")

            if not data:
                return

            # Bybit can theoretically send multiple trades
            # in one websocket message.
            with self._locks[symbol]:

                for trade in data:

                    timestamp = datetime.fromtimestamp(
                        int(trade["T"]) / 1000,
                        tz=timezone.utc
                    )

                    state = self._get_or_create_state(
                        symbol,
                        timestamp,
                    )

                    size = Decimal(str(trade["v"]))

                    # Bybit:
                    # S == Buy  -> positive CVD
                    # S == Sell -> negative CVD
                    if trade["S"] == "Buy":
                        state.cvd_delta += size
                    else:
                        state.cvd_delta -= size

                    state.trade_count += 1

        except Exception:
            logger.exception(
                "Trade handler error"
            )

    # ------------------------------------------------------------------
    # TICKER
    # ------------------------------------------------------------------

    def handle_ticker(self, msg: dict) -> None:
        """
        Process ticker updates.

        Last ticker received inside the period is used.
        """

        try:
            topic = msg.get("topic", "")
            symbol = topic.removeprefix("tickers.")

            if symbol not in self.coins:
                return

            data = msg.get("data")

            if not data:
                return

            timestamp = datetime.fromtimestamp(
                int(msg["ts"]) / 1000,
                tz=timezone.utc
            )

            ticker = Ticker(
                timestamp=timestamp,
                **data,
            )

            with self._locks[symbol]:

                state = self._get_or_create_state(
                    symbol,
                    timestamp,
                )

                state.ticker = ticker

        except Exception:
            logger.exception(
                "Ticker handler error"
            )

    # ------------------------------------------------------------------
    # KLINE
    # ------------------------------------------------------------------

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
                return

            symbol = parts[-1]

            coin = self.coins.get(symbol)

            if coin is None:
                return

            data_list = msg.get("data")

            if not data_list:
                return

            data = data_list[0]

            kline = Kline(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(
                    int(data["start"]) / 1000,
                    tz=timezone.utc
                ),
                open=Decimal(str(data["open"])),
                high=Decimal(str(data["high"])),
                low=Decimal(str(data["low"])),
                close=Decimal(str(data["close"])),
                volume=Decimal(str(data["volume"])),
                turnover=Decimal(
                    str(data.get("turnover", 0))
                ),
            )

            with self._locks[symbol]:
                if data.get("confirm"):
                    coin.add_kline(kline)

                elif coin.klines:
                    last = coin.klines[-1]

                    if last.timestamp == kline.timestamp:
                        coin.klines[-1] = kline
                    elif kline.timestamp > last.timestamp:
                        coin.add_kline(kline)

        except Exception as exception:
            logger.exception(f"Kline handler error: {exception}")

    # ------------------------------------------------------------------
    # WEBSOCKET
    # ------------------------------------------------------------------

    def _create_connection(
        self,
        symbols: list[str],
    ) -> WebSocket:

        ws = WebSocket(
            testnet=False,
            channel_type="linear",
        )

        # --------------------------------------------------------------
        # One subscription request for ALL klines
        # --------------------------------------------------------------

        ws.subscribe(
            topic=f"kline.{self.interval}." + "{symbol}",
            symbol=symbols,
            callback=self.handle_kline,
        )

        # --------------------------------------------------------------
        # One subscription request for ALL trades
        # --------------------------------------------------------------

        ws.subscribe(
            topic="publicTrade.{symbol}",
            symbol=symbols,
            callback=self.handle_trade,
        )

        # --------------------------------------------------------------
        # One subscription request for ALL tickers
        # --------------------------------------------------------------

        ws.subscribe(
            topic="tickers.{symbol}",
            symbol=symbols,
            callback=self.handle_ticker,
        )

        return ws

    # ------------------------------------------------------------------
    # START
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start websocket streams.

        Symbols are split between several WebSocket connections.
        """

        symbols = list(self.coins)

        if not symbols:
            logger.warning(
                "No symbols to subscribe"
            )
            return

        logger.info(
            "Starting market stream: "
            "%d symbols, interval=%dm, chunk=%d",
            len(symbols),
            self.interval,
            self.chunk_size,
        )

        for start in range(
            0,
            len(symbols),
            self.chunk_size,
        ):

            chunk = symbols[
                start:start + self.chunk_size
            ]

            ws = self._create_connection(
                chunk
            )

            self.ws_connections.append(ws)

            logger.info(
                "WebSocket #%d: %d symbols",
                len(self.ws_connections),
                len(chunk),
            )

        logger.info(
            "Market stream started: %d WebSockets",
            len(self.ws_connections),
        )

    # ------------------------------------------------------------------
    # CLOSE
    # ------------------------------------------------------------------

    def close_all_periods(self) -> None:
        """
        Persist all currently active periods.
        """

        for symbol, lock in self._locks.items():

            with lock:

                state = self._states.pop(
                    symbol,
                    None,
                )

                if state is None:
                    continue

                if (
                    state.cvd_delta
                    or state.ticker is not None
                    or state.trade_count
                ):
                    self._persist_period(
                        symbol,
                        state,
                    )

                    logger.info(
                        "[%s] Final period closed: %d trades",
                        symbol,
                        state.trade_count,
                    )

    # ------------------------------------------------------------------
    # STOP
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """
        Close websocket connections.
        """

        self.close_all_periods()

        for ws in self.ws_connections:

            try:
                ws.exit()
            except Exception:
                logger.exception(
                    "Error closing WebSocket"
                )

        self.ws_connections.clear()

        logger.info(
            "Market data stream stopped"
        )
