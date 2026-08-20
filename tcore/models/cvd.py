from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CVD(BaseModel):
    """Cumulative Volume Delta (кумулятивная дельта объёма)."""
    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    timestamp: datetime
    value: Decimal
    delta: Decimal
