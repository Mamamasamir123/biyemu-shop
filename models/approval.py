from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ApprovalType(str, Enum):
    ADD_PRODUCT = "add_product"
    DELETE_PRODUCT = "delete_product"
    DELETE_SALE = "delete_sale"
    BULK_PRICE_CHANGE = "bulk_price_change"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    id: str
    approval_type: ApprovalType
    requested_by: str
    requester_name: str
    shop_id: str
    details: str
    target_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    boss_note: str = ""
    created_at: str = ""
    approver_role: str = "boss"
    payload: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "approval_type": self.approval_type.value,
            "requested_by": self.requested_by,
            "requester_name": self.requester_name,
            "shop_id": self.shop_id,
            "details": self.details,
            "target_id": self.target_id,
            "status": self.status.value,
            "boss_note": self.boss_note,
            "created_at": self.created_at,
            "approver_role": self.approver_role,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ApprovalRequest":
        return cls(
            id=data["id"],
            approval_type=ApprovalType(data["approval_type"]),
            requested_by=data["requested_by"],
            requester_name=data["requester_name"],
            shop_id=data["shop_id"],
            details=data["details"],
            target_id=data["target_id"],
            status=ApprovalStatus(data.get("status", "pending")),
            boss_note=data.get("boss_note", ""),
            created_at=data.get("created_at", ""),
            approver_role=data.get("approver_role", "boss"),
            payload=data.get("payload", ""),
        )