from decimal import Decimal
from math import sqrt
from typing import Optional

from tcore.models.kline import Kline


def _closes(klines: list[Kline]) -> list[Decimal]:
    return [k.close for k in klines]


def ema(values: list[Decimal], period: int) -> Optional[Decimal]:
    if len(values) < period:
        return None

    result = sum(values[:period], Decimal(0)) / period
    multiplier = Decimal(2) / (period + 1)

    for value in values[period:]:
        result += (value - result) * multiplier

    return result


def sma(klines: list[Kline], period: int = 50) -> Optional[Decimal]:
    if len(klines) < period:
        return None

    return sum((k.close for k in klines[-period:]), Decimal(0)) / period


def rsi(klines: list[Kline], period: int = 14) -> Optional[Decimal]:
    if len(klines) < period + 1:
        return None

    closes = _closes(klines)
    gains, losses = [], []

    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, Decimal(0)))
        losses.append(max(-change, Decimal(0)))

    avg_gain = sum(gains[:period], Decimal(0)) / period
    avg_loss = sum(losses[:period], Decimal(0)) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return Decimal(100) if avg_gain else Decimal(50)

    rs = avg_gain / avg_loss
    return Decimal(100) - Decimal(100) / (Decimal(1) + rs)


def macd(
        klines: list[Kline],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
) -> Optional[tuple[Decimal, Decimal, Decimal]]:
    if len(klines) < slow + signal - 1:
        return None

    closes = _closes(klines)

    fast_ema = []
    slow_ema = []

    fast_value = sum(closes[:fast], Decimal(0)) / fast
    slow_value = sum(closes[:slow], Decimal(0)) / slow

    fast_mult = Decimal(2) / (fast + 1)
    slow_mult = Decimal(2) / (slow + 1)

    for i, close in enumerate(closes):
        if i >= fast:
            fast_value += (close - fast_value) * fast_mult

        if i >= fast - 1:
            fast_ema.append(fast_value)

        if i >= slow:
            slow_value += (close - slow_value) * slow_mult

        if i >= slow - 1:
            slow_ema.append(slow_value)

    offset = slow - fast
    macd_values = [f - s for f, s in zip(fast_ema[offset:], slow_ema)]

    macd_value = macd_values[-1]
    signal_value = ema(macd_values, signal)

    if signal_value is None:
        return None

    return macd_value, signal_value, macd_value - signal_value


def mfi(klines: list[Kline], period: int = 14) -> Optional[Decimal]:
    if len(klines) < period + 1:
        return None

    values = []

    for k in klines:
        typical = (k.high + k.low + k.close) / 3
        values.append((typical, typical * k.volume))

    positive = negative = Decimal(0)

    for i in range(-period, 0):
        current_price, flow = values[i]
        previous_price = values[i - 1][0]

        if current_price > previous_price:
            positive += flow
        elif current_price < previous_price:
            negative += flow

    if negative == 0:
        return Decimal(100)

    ratio = positive / negative
    return Decimal(100) - Decimal(100) / (Decimal(1) + ratio)


def cci(klines: list[Kline], period: int = 20) -> Optional[Decimal]:
    if len(klines) < period:
        return None

    values = [(k.high + k.low + k.close) / 3 for k in klines[-period:]]

    mean = sum(values, Decimal(0)) / period
    deviation = sum(
        (abs(v - mean) for v in values),
        Decimal(0)
    ) / period

    if deviation == 0:
        return Decimal(0)

    return (values[-1] - mean) / (Decimal(0.015) * deviation)


def bollinger_bands(
    klines: list[Kline],
    period: int = 20,
    deviations: Decimal = Decimal(2)
) -> Optional[tuple[Decimal, Decimal, Decimal]]:
    if len(klines) < period:
        return None

    closes = [k.close for k in klines[-period:]]

    middle = sum(closes, Decimal(0)) / period
    variance = sum((x - middle) ** 2 for x in closes) / period
    std = Decimal(sqrt(variance))

    return middle + deviations * std, middle, middle - deviations * std


def williams_r(klines: list[Kline], period: int = 14) -> Optional[Decimal]:
    if len(klines) < period:
        return None

    values = klines[-period:]
    highest = max(k.high for k in values)
    lowest = min(k.low for k in values)

    if highest == lowest:
        return Decimal(0)

    return Decimal(-100) * (highest - values[-1].close) / (highest - lowest)


def stoch_rsi(klines: list[Kline], period: int = 14) -> Optional[Decimal]:
    if len(klines) < period * 2:
        return None

    closes = _closes(klines)
    gains, losses = [], []

    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, Decimal(0)))
        losses.append(max(-change, Decimal(0)))

    avg_gain = sum(gains[:period], Decimal(0)) / period
    avg_loss = sum(losses[:period], Decimal(0)) / period
    rsi_values = []

    def calc_rsi(gain: Decimal, loss: Decimal) -> Decimal:
        if loss == 0:
            return Decimal(100) if gain else Decimal(50)

        return Decimal(100) - Decimal(100) / (Decimal(1) + gain / loss)

    rsi_values.append(calc_rsi(avg_gain, avg_loss))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi_values.append(calc_rsi(avg_gain, avg_loss))

    if len(rsi_values) < period:
        return None

    values = rsi_values[-period:]
    low, high = min(values), max(values)

    if high == low:
        return Decimal(0)

    return (values[-1] - low) / (high - low)


def adx(klines: list[Kline], period: int = 14) -> Optional[Decimal]:
    if len(klines) < period * 2:
        return None

    trs, plus_dms, minus_dms = [], [], []

    for current, previous in zip(klines[1:], klines[:-1]):
        tr = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close)
        )

        up = current.high - previous.high
        down = previous.low - current.low

        trs.append(tr)
        plus_dms.append(up if up > down and up > 0 else Decimal(0))
        minus_dms.append(down if down > up and down > 0 else Decimal(0))

    atr = sum(trs[:period], Decimal(0)) / period
    plus_dm = sum(plus_dms[:period], Decimal(0)) / period
    minus_dm = sum(minus_dms[:period], Decimal(0)) / period

    dx_values = []

    def dx() -> Decimal:
        if atr == 0:
            return Decimal(0)

        plus_di = Decimal(100) * plus_dm / atr
        minus_di = Decimal(100) * minus_dm / atr
        total = plus_di + minus_di

        if total == 0:
            return Decimal(0)

        return Decimal(100) * abs(plus_di - minus_di) / total

    dx_values.append(dx())

    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
        plus_dm = (plus_dm * (period - 1) + plus_dms[i]) / period
        minus_dm = (minus_dm * (period - 1) + minus_dms[i]) / period
        dx_values.append(dx())

    if len(dx_values) < period:
        return None

    result = sum(dx_values[:period], Decimal(0)) / period

    for value in dx_values[period:]:
        result = (result * (period - 1) + value) / period

    return result


def roi(klines: list[Kline], period: int = 14) -> Optional[Decimal]:
    if len(klines) < period:
        return None

    first = klines[-period].close
    last = klines[-1].close

    if first == 0:
        return None

    return (last - first) / first * 100
