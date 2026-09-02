from dataclasses import dataclass


@dataclass(slots=True)
class DBServiceConfig(object):
    path: str
    buffer_size: int = 60
    flush_interval: int = 120

    @property
    def url(self) -> str:
        return f"sqlite+aiosqlite:///{self.path}"
