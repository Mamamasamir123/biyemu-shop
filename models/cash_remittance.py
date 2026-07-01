from dataclasses import dataclass, field
from enum import Enum


class RemittanceStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@dataclass
class CashRemittance:
    id: str
    shop_id: str
    employee_id: str
    employee_name: str
    receiver_id: str
    receiver_name: str
    receiver_role: str
    amount: float
    sale_ids: list[str] = field(default_factory=list)
    status: RemittanceStatus = RemittanceStatus.PENDING
    remittance_kind: str = "from_employee"
    note: str = ""
    created_at: str = ""
    confirmed_at: str = ""
    confirmed_by_id: str = ""
    confirmed_by_name: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "shop_id": self.shop_id,
            "employee_id": self.employee_id,
            "employee_name": self.employee_name,
            "receiver_id": self.receiver_id,
            "receiver_name": self.receiver_name,
            "receiver_role": self.receiver_role,
            "amount": self.amount,
            "sale_ids": self.sale_ids,
            "status": self.status.value,
            "remittance_kind": self.remittance_kind,
            "note": self.note,
            "created_at": self.created_at,
            "confirmed_at": self.confirmed_at,
            "confirmed_by_id": self.confirmed_by_id,
            "confirmed_by_name": self.confirmed_by_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CashRemittance":
        return cls(
            id=data["id"],
            shop_id=data["shop_id"],
            employee_id=data["employee_id"],
            employee_name=data["employee_name"],
            receiver_id=data.get("receiver_id", ""),
            receiver_name=data.get("receiver_name", ""),
            receiver_role=data.get("receiver_role", "manager"),
            amount=float(data.get("amount", 0)),
            sale_ids=list(data.get("sale_ids", [])),
            status=RemittanceStatus(data.get("status", "pending")),
            remittance_kind=data.get("remittance_kind", "from_employee"),
            note=data.get("note", ""),
            created_at=data.get("created_at", ""),
            confirmed_at=data.get("confirmed_at", ""),
            confirmed_by_id=data.get("confirmed_by_id", ""),
            confirmed_by_name=data.get("confirmed_by_name", ""),
        )