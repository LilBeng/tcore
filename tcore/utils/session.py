from pybit.unified_trading import HTTP
from requests.adapters import HTTPAdapter
from urllib3 import Retry


class Session(HTTP):
    def __init__(
            self,
            pool_connections: int = 10,
            pool_maxsize: int = 30,
            max_retries: int = 3,
            backoff_factor: float = 0.1,
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

        self.client.mount("://", adapter)
