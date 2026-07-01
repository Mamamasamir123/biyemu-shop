from dataclasses import dataclass


@dataclass
class ChatMessage:
    id: str
    sender_id: str
    receiver_id: str
    body: str
    created_at: str
    read_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "body": self.body,
            "created_at": self.created_at,
            "read_at": self.read_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        return cls(
            id=data["id"],
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            body=data.get("body", ""),
            created_at=data.get("created_at", ""),
            read_at=data.get("read_at", ""),
        )