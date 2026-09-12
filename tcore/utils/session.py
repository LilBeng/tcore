from pybit.unified_trading import HTTP
from requests.adapters import HTTPAdapter
from urllib3 import Retry


class Session(HTTP):
    def __init__(
            self,
            pool_connections: int,
            pool_maxsize: int,
            max_retries: int,
            backoff_factor: float,
            **args) -> None:
        super().__init__(**args)

        adapter = HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=Retry(
                total=max_retries,
                backoff_factor=backoff_factor
            )
        )

        self.client.mount("https://api.bybit.com", adapter)
        self.client.mount("https://api-testnet.bybit.com", adapter)
