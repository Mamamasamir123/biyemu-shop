from dataclasses import dataclass
from enum import Enum


class ConnectionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class StaffConnection:
    id: str
    requester_id: str
    target_id: str
    status: ConnectionStatus
    created_at: str
    responded_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "requester_id": self.requester_id,
            "target_id": self.target_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "responded_at": self.responded_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StaffConnection":
        return cls(
            id=data["id"],
            requester_id=data["requester_id"],
            target_id=data["target_id"],
            status=ConnectionStatus(data.get("status", "pending")),
            created_at=data.get("created_at", ""),
            responded_at=data.get("responded_at", ""),
        )