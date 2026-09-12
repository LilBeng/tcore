from enum import Enum
from typing import Optional


class InstrumentStatus(str, Enum):
    """Статус инструмента"""
    PRE_LAUNCH = "PreLaunch"
    TRADING = "Trading"
    DELIVERING = "Delivering"
    CLOSED = "Closed"


class Category(str, Enum):
    SPOT = "spot"
    LINEAR = "linear"
    INVERSE = "inverse"
    OPTION = "option"


class KlineInterval(str, Enum):
    M1 = "1"      # 1 минута
    M3 = "3"      # 3 минуты
    M5 = "5"      # 5 минут
    M15 = "15"    # 15 минут
    M30 = "30"    # 30 минут
    H1 = "60"     # 1 час
    H2 = "120"    # 2 часа
    H4 = "240"    # 4 часа
    H6 = "360"    # 6 часов
    H12 = "720"   # 12 часов
    D1 = "D"      # 1 день
    W1 = "W"      # 1 неделя
    MN1 = "M"     # 1 месяц


class OIInterval(str, Enum):
    M5 = "5min"    # 5 минут
    M15 = "15min"  # 15 минут
    M30 = "30min"  # 30 минут
    H1 = "1h"      # 1 час
    H4 = "4h"      # 4 часа
    D1 = "1d"      # 1 день


class OrderSide(str, Enum):
    BUY = "Buy"  # Мейкер купил (Тейкер продал)
    SELL = "Sell"  # Мейкер продал (Тейкер купил)


class MarketInterval(int, Enum):
    M1 = 1  # 1 минута
    M3 = 3  # 3 минуты
    M5 = 5  # 5 минут
    M15 = 15  # 15 минут
    M30 = 30  # 30 минут
    H1 = 60  # 1 час
    H2 = 120  # 2 часа
    H4 = 240  # 4 часа
    H6 = 360  # 6 часов
    H12 = 720  # 12 часов
    H24 = 1440  # 24 часа

    @property
    def kline_interval(self) -> KlineInterval:
        match self.value:
            case self.M1:
                return KlineInterval.M1
            case self.M3:
                return KlineInterval.M3
            case self.M5:
                return KlineInterval.M5
            case self.M15:
                return KlineInterval.M15
            case self.M30:
                return KlineInterval.M30
            case self.H1:
                return KlineInterval.H1
            case self.H2:
                return KlineInterval.H2
            case self.H4:
                return KlineInterval.H4
            case self.H6:
                return KlineInterval.H6
            case self.H12:
                return KlineInterval.H12

    @property
    def oi_interval(self) -> Optional[OIInterval]:
        match self.value:
            case self.M1:
                return None
            case self.M3:
                return None
            case self.M5:
                return OIInterval.M5
            case self.M15:
                return OIInterval.M15
            case self.M30:
                return OIInterval.M30
            case self.H1:
                return OIInterval.H1
            case self.H2:
                return None
            case self.H4:
                return OIInterval.H4
            case self.H6:
                return None
            case self.H12:
                return None


class EventType(Enum):
    KLINE = 0
    TRADE = 1
    TICKER = 2


class DataType(int, Enum):
    KLINE = 0
    OPEN_INTEREST = 1
    FUNDING_RATE = 2
    CVD = 3


class SignalStatus(Enum):
    TRACKING = 0
    NOT_SUITABLE = 1
    ENTRY = 2
    WAITING = 3
