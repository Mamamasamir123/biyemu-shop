import uuid
from datetime import datetime, timedelta
from typing import Optional

from models.notification import (
    DEFAULT_NOTIFICATION_PREFS,
    NOTIFICATION_PREF_KEYS,
    Notification,
    NotificationType,
)
from models.user import User, UserRole
from services.boss_settings_service import ARCHIVE_RETENTION_DAYS
from storage.json_storage import JsonStorage


class NotificationService:
    LOW_STOCK_THRESHOLD = 5

    def __init__(self, storage: JsonStorage, user_service, boss_settings_service=None):
        self.storage = storage
        self.user_service = user_service
        self.boss_settings = boss_settings_service

    def get_all(self) -> list[Notification]:
        return self.storage.load_list("notifications", Notification.from_dict)

    def get_for_user(self, user_id: str, *, unread_only: bool = False) -> list[Notification]:
        items = [n for n in self.get_all() if n.user_id == user_id]
        if unread_only:
            items = [n for n in items if not n.read]
        return sorted(items, key=lambda n: n.created_at, reverse=True)

    def get_unread_count(self, user_id: str) -> int:
        return len(self.get_for_user(user_id, unread_only=True))

    def send(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        link: str = "",
        meta: dict | None = None,
    ) -> Optional[Notification]:
        user = self.user_service.get_by_id(user_id)
        if not user:
            return None
        if (
            user.is_boss()
            and self.boss_settings
            and self.boss_settings.is_notifications_muted()
        ):
            return None
        prefs = self.get_user_prefs(user)
        if not prefs.get(notification_type, True):
            return None
        note = Notification(
            id=str(uuid.uuid4())[:8],
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            meta=meta,
        )
        items = self.get_all()
        items.append(note)
        self.storage.save_list("notifications", items)
        return note

    def mark_read(self, notification_id: str, user_id: str) -> bool:
        items = self.get_all()
        for i, note in enumerate(items):
            if note.id == notification_id and note.user_id == user_id:
                items[i].read = True
                self.storage.save_list("notifications", items)
                return True
        return False

    def mark_all_read(self, user_id: str) -> int:
        items = self.get_all()
        count = 0
        for i, note in enumerate(items):
            if note.user_id == user_id and not note.read:
                items[i].read = True
                count += 1
        if count:
            self.storage.save_list("notifications", items)
        return count

    def get_user_prefs(self, user: User) -> dict[str, bool]:
        prefs = dict(DEFAULT_NOTIFICATION_PREFS)
        if user.notification_prefs:
            prefs.update(user.notification_prefs)
        return prefs

    def update_user_prefs(self, user_id: str, prefs: dict[str, bool]) -> dict[str, bool]:
        clean = dict(DEFAULT_NOTIFICATION_PREFS)
        for key in NOTIFICATION_PREF_KEYS:
            if key in prefs:
                clean[key] = bool(prefs[key])
        self.user_service.update_notification_prefs(user_id, clean)
        return clean

    def notify_users(
        self,
        user_ids: list[str],
        notification_type: str,
        title: str,
        message: str,
        link: str = "",
        meta: dict | None = None,
    ) -> None:
        for user_id in user_ids:
            self.send(user_id, notification_type, title, message, link, meta=meta)

    def recipients_for_approval(self, approver_role: str, shop_id: str) -> list[str]:
        if approver_role == UserRole.BOSS.value:
            return [u.id for u in self.user_service.get_all() if u.role == UserRole.BOSS]
        return [
            u.id
            for u in self.user_service.get_all()
            if u.role == UserRole.MANAGER and u.shop_id == shop_id
        ]

    def recipients_for_shop_managers(self, shop_id: str) -> list[str]:
        ids = [u.id for u in self.user_service.get_all() if u.role == UserRole.BOSS]
        ids.extend(
            u.id
            for u in self.user_service.get_all()
            if u.role == UserRole.MANAGER and u.shop_id == shop_id
        )
        return list(dict.fromkeys(ids))

    def _get_archive(self) -> list[dict]:
        return self.storage.load_dict("notification_archive").get("items", [])

    def _save_archive(self, items: list[dict]) -> None:
        self.storage.save_dict("notification_archive", {"items": items})

    def purge_expired_archive(self) -> int:
        cutoff = datetime.now() - timedelta(days=ARCHIVE_RETENTION_DAYS)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M")
        items = self._get_archive()
        kept = [i for i in items if i.get("archived_at", "") >= cutoff_str]
        removed = len(items) - len(kept)
        if removed:
            self._save_archive(kept)
        return removed

    def archive_user_notifications(self, user_id: str) -> int:
        self.purge_expired_archive()
        items = self.get_all()
        to_archive = [n for n in items if n.user_id == user_id]
        if not to_archive:
            return 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        archive = self._get_archive()
        for note in to_archive:
            archive.append(
                {
                    **note.to_dict(),
                    "archived_at": now,
                }
            )
        self._save_archive(archive)
        remaining = [n for n in items if n.user_id != user_id]
        self.storage.save_list("notifications", remaining)
        return len(to_archive)

    def get_archived_for_user(self, user_id: str) -> list[dict]:
        self.purge_expired_archive()
        items = [i for i in self._get_archive() if i.get("user_id") == user_id]
        return sorted(items, key=lambda i: i.get("archived_at", ""), reverse=True)