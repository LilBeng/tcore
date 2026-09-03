import os
from dataclasses import dataclass
from datetime import timedelta, datetime

from tcore.models.enums import Category, MarketInterval


@dataclass(slots=True)
class MarketConfig(object):
    # Update
    instruments_update_timedelta: timedelta

    # Database
    database_folder_path: str
    max_records: int = 50_000
    buffer_size: int = 60
    flush_interval: int = 120

    # Bybit
    test_net: bool = False
    category: Category = Category.LINEAR
    interval: MarketInterval = MarketInterval.M5
    max_subscribe_size: int = 50
    oi_history_limit: int = 400
    klines_history_limit: int = 1000

    # HTTP
    pool_connections: int = 100
    pool_maxsize: int = 100
    backoff_factor: float = 0.1
    max_retries: int = 3

    # Memory
    max_list_len: int = 25_000

    def __post_init__(self) -> None:
        os.makedirs(os.path.dirname(self.database_folder_path), exist_ok=True)

        assert self.max_subscribe_size <= 50

    @property
    def url_datetime(self) -> str:
        filepath = os.path.join(self.database_folder_path, f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}")
        return f"sqlite+aiosqlite:///{filepath}"
