from dataclasses import dataclass
from enum import Enum


class NotificationType(str, Enum):
    APPROVAL_INCOMING = "approval_incoming"
    APPROVAL_RESULT = "approval_result"
    SALE_NEW = "sale_new"
    LOW_STOCK = "low_stock"
    STAFF = "staff"
    CASH_REMITTANCE = "cash_remittance"


DEFAULT_NOTIFICATION_PREFS: dict[str, bool] = {
    NotificationType.APPROVAL_INCOMING.value: True,
    NotificationType.APPROVAL_RESULT.value: True,
    NotificationType.SALE_NEW.value: True,
    NotificationType.LOW_STOCK.value: True,
    NotificationType.STAFF.value: True,
    NotificationType.CASH_REMITTANCE.value: True,
}


NOTIFICATION_PREF_KEYS = list(DEFAULT_NOTIFICATION_PREFS.keys())


@dataclass
class Notification:
    id: str
    user_id: str
    notification_type: str
    title: str
    message: str
    link: str = ""
    read: bool = False
    created_at: str = ""
    meta: dict | None = None

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "notification_type": self.notification_type,
            "title": self.title,
            "message": self.message,
            "link": self.link,
            "read": self.read,
            "created_at": self.created_at,
        }
        if self.meta:
            data["meta"] = self.meta
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Notification":
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            notification_type=data["notification_type"],
            title=data["title"],
            message=data["message"],
            link=data.get("link", ""),
            read=data.get("read", False),
            created_at=data.get("created_at", ""),
            meta=data.get("meta"),
        )