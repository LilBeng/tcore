from collections import deque

from tcore.models.cvd import CVD
from tcore.models.funding import FundingRate
from tcore.models.instrument import Instrument, RiskParameters
from tcore.models.kline import Kline
from tcore.models.oi import OpenInterest
from tcore.models.tick import Ticker


class Coin(object):
    def __init__(
            self,
            instrument: Instrument,
            ticker: Ticker,
            klines: list[Kline],
            open_interests: list[OpenInterest],
            funding_rates: list[FundingRate],
            cvds: list[CVD],
            max_len: int = 10000
    ) -> None:
        """
        Инициализация объекта монеты/торгового инструмента.

        Args:
            instrument: Торговый инструмент (символ, параметры контракта)
            ticker: Рыночные данные
            klines: Список исторических свечей
            open_interests: Список данных по открытому интересу (OI)
            funding_rates: Список ставок финансирования
            cvds: Список данных по кумулятивному объему дельта (CVD)
            max_len: Максимальный размер очередей (по умолчанию 10000)
                   При превышении старые данные автоматически удаляются
        """
        self.instrument = instrument
        self.ticker = ticker
        self.klines = deque(klines, max_len)
        self.open_interests = deque(open_interests, max_len)
        self.funding_rates = deque(funding_rates, max_len)
        self.cvds = deque(cvds, max_len)

    def has_risk(self, risk_parameters: RiskParameters) -> bool:
        """
        Проверяет, есть ли риск по торговому инструменту.

        Сравнивает ценовые коэффициенты инструмента с допустимыми лимитами.
        Если оба коэффициента инструмента меньше или равны лимитам -> риск ЕСТЬ.

        Args:
            risk_parameters: Параметры риска с лимитами (price_limit_ratio_x/y)

        Returns:
            bool: True - риск есть (сделку лучше не открывать),
                  False - риска нет (сделка безопасна)
        """
        ratio_x = self.instrument.risk_parameters.price_limit_ratio_x <= risk_parameters.price_limit_ratio_x
        ratio_y = self.instrument.risk_parameters.price_limit_ratio_y <= risk_parameters.price_limit_ratio_y
        return ratio_x and ratio_y

    def update_instrument_data(self, instrument: Instrument) -> None:
        """
        Обновляет данные торгового инструмента.

        Используется, когда параметры инструмента изменились
        (например, обновились лимиты, шаг цены и т.д.)

        Args:
            instrument: Новый объект инструмента с обновленными параметрами
        """
        self.instrument = instrument

    def update_ticker(self, ticker: Ticker) -> None:
        """
        Обновляет тикер (текущие рыночные данные) инструмента.

        Тикер содержит актуальную информацию о цене инструмента в реальном времени:
        - цена последней сделки (last_price)
        - лучшая цена покупки (bid_price) и продажи (ask_price)
        - максимальная/минимальная цена за 24 часа
        - объем торгов за 24 часа
        - изменение цены в процентах и т.д.

        Этот метод вызывается при каждом обновлении рыночной информации
        (обычно через WebSocket или периодические REST-запросы).

        Args:
            ticker: Новый объект Ticker с актуальными рыночными данными
        """
        self.ticker = ticker

    def add_kline(self, kline: Kline) -> None:
        """
        Добавляет новую свечу в историю.

        Если очередь достигла max_len, самая старая свеча удаляется автоматически.

        Args:
            kline: Новая свеча (цена открытия, закрытия, объем и т.д.)
        """
        self.klines.append(kline)

    def add_open_interest(self, open_interest: OpenInterest) -> None:
        """
        Добавляет новую запись по открытому интересу (Open Interest).

        Open Interest - общее количество открытых контрактов.
        Используется для анализа активности рынка.

        Args:
            open_interest: Данные по открытому интересу (время, значение)
        """
        self.open_interests.append(open_interest)

    def add_funding_rate(self, funding_rate: FundingRate) -> None:
        """
        Добавляет новую ставку финансирования.

        Ставка финансирования - периодический платеж между трейдерами
        для привязки цены фьючерса к спотовой цене.

        Args:
            funding_rate: Ставка финансирования (время, значение)
        """
        self.funding_rates.append(funding_rate)

    def add_cvd(self, cvd: CVD) -> None:
        """
        Добавляет новую запись по кумулятивному объему дельта (CVD).

        CVD показывает разницу между рыночными покупками и продажами
        нарастающим итогом. Используется для оценки давления покупателей/продавцов.

        Args:
            cvd: Данные по CVD (время, значение)
        """
        self.cvds.append(cvd)
