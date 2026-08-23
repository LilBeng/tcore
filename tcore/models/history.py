from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from tcore.models.enums import OrderSide


@dataclass(slots=True)
class TradeHistory:
    exec_id: str
    price: Decimal
    size: Decimal
    side: OrderSide
    timestamp: datetime
    is_block_trade: bool
    is_rpi_trade: bool
    seq: str

    @classmethod
    def from_api(cls, data: dict) -> "TradeHistory":
        return cls(
            exec_id=data["execId"],
            price=Decimal(data["price"]),
            size=Decimal(data["size"]),
            side=OrderSide(data["side"]),
            timestamp=datetime.fromtimestamp(int(data["time"]) / 1000, timezone.utc),
            is_block_trade=data["isBlockTrade"],
            is_rpi_trade=data["isRPITrade"],
            seq=data["seq"]
        )

    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        return self.side == OrderSide.SELL

    @property
    def volume_usdt(self) -> Decimal:
        return self.price * self.size
