from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrashItem:
    id: str
    item_type: str
    data: dict
    shop_id: str
    deleted_by: str
    deleted_by_name: str
    deleted_at: str
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "item_type": self.item_type,
            "data": self.data,
            "shop_id": self.shop_id,
            "deleted_by": self.deleted_by,
            "deleted_by_name": self.deleted_by_name,
            "deleted_at": self.deleted_at,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrashItem":
        return cls(
            id=data["id"],
            item_type=data["item_type"],
            data=data.get("data", {}),
            shop_id=data.get("shop_id", ""),
            deleted_by=data.get("deleted_by", ""),
            deleted_by_name=data.get("deleted_by_name", ""),
            deleted_at=data.get("deleted_at", ""),
            reason=data.get("reason", ""),
        )