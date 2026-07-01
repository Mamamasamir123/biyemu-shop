from dataclasses import dataclass
from enum import Enum


class DashboardResetStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class DashboardResetRequest:
    id: str
    target_user_id: str
    target_user_name: str
    target_role: str
    shop_id: str
    section: str
    requested_by: str
    requester_name: str
    status: DashboardResetStatus = DashboardResetStatus.PENDING
    created_at: str = ""
    responded_at: str = ""
    response_note: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "target_user_id": self.target_user_id,
            "target_user_name": self.target_user_name,
            "target_role": self.target_role,
            "shop_id": self.shop_id,
            "section": self.section,
            "requested_by": self.requested_by,
            "requester_name": self.requester_name,
            "status": self.status.value,
            "created_at": self.created_at,
            "responded_at": self.responded_at,
            "response_note": self.response_note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DashboardResetRequest":
        return cls(
            id=data["id"],
            target_user_id=data["target_user_id"],
            target_user_name=data["target_user_name"],
            target_role=data["target_role"],
            shop_id=data.get("shop_id", ""),
            section=data["section"],
            requested_by=data["requested_by"],
            requester_name=data["requester_name"],
            status=DashboardResetStatus(data.get("status", "pending")),
            created_at=data.get("created_at", ""),
            responded_at=data.get("responded_at", ""),
            response_note=data.get("response_note", ""),
        )