from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class User:
    id: Optional[int] = None
    is_active: bool = True
    risk_percent: float = 3
    max_position_percent: float = 1
    max_daily_loss_percent: float = 1
    max_open_positions: int = 5

    created_at: Optional[datetime] = None


@dataclass(slots=True)
class ExchangeAccount:
    user_id: int
    name: str
    api_key: str
    api_secret: str
    id: Optional[int] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
