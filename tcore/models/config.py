from pydantic import BaseModel


class DBServiceConfig(BaseModel):
    path: str
    buffer_size: int = 60
    flush_interval: int = 120

    @property
    def url(self) -> str:
        return f"sqlite+aiosqlite:///{self.path}"
