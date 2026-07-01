import uuid
from datetime import datetime
from typing import Optional

from models.chat_message import ChatMessage
from storage.json_storage import JsonStorage


class ChatService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def get_all(self) -> list[ChatMessage]:
        return self.storage.load_list("chat_messages", ChatMessage.from_dict)

    def _pair_key(self, user_a: str, user_b: str) -> tuple[str, str]:
        return tuple(sorted((user_a, user_b)))

    def _is_between(self, msg: ChatMessage, user_a: str, user_b: str) -> bool:
        return {msg.sender_id, msg.receiver_id} == {user_a, user_b}

    def get_conversation(self, user_id: str, partner_id: str) -> list[ChatMessage]:
        items = [m for m in self.get_all() if self._is_between(m, user_id, partner_id)]
        return sorted(items, key=lambda m: m.created_at)

    def get_last_message_between(
        self, user_id: str, partner_id: str
    ) -> Optional[ChatMessage]:
        items = self.get_conversation(user_id, partner_id)
        return items[-1] if items else None

    def send_message(self, sender_id: str, receiver_id: str, body: str) -> ChatMessage:
        body = (body or "").strip()
        if not body:
            raise ValueError("Ujumbe hauna maudhui.")
        msg = ChatMessage(
            id=str(uuid.uuid4())[:8],
            sender_id=sender_id,
            receiver_id=receiver_id,
            body=body,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        messages = self.get_all()
        messages.append(msg)
        self.storage.save_list("chat_messages", messages)
        return msg

    def get_unread_count(self, user_id: str) -> int:
        return sum(
            1
            for m in self.get_all()
            if m.receiver_id == user_id and not m.read_at
        )

    def get_unread_count_from(self, user_id: str, partner_id: str) -> int:
        return sum(
            1
            for m in self.get_all()
            if m.receiver_id == user_id
            and m.sender_id == partner_id
            and not m.read_at
        )

    def mark_read(self, user_id: str, partner_id: str) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        messages = self.get_all()
        updated = 0
        for i, msg in enumerate(messages):
            if (
                msg.receiver_id == user_id
                and msg.sender_id == partner_id
                and not msg.read_at
            ):
                messages[i].read_at = now
                updated += 1
        if updated:
            self.storage.save_list("chat_messages", messages)
        return updated