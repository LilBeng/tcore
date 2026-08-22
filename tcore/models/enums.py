from enum import Enum


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
