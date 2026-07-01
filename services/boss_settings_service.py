from datetime import datetime, timedelta

from storage.json_storage import JsonStorage

ARCHIVE_RETENTION_DAYS = 30
DEFAULT_SETTINGS = {
    "notifications_muted": False,
    "notifications_muted_at": "",
}


class BossSettingsService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def _load(self) -> dict:
        data = self.storage.load_dict("system_settings")
        return {**DEFAULT_SETTINGS, **data}

    def _save(self, data: dict) -> None:
        self.storage.save_dict("system_settings", data)

    def is_notifications_muted(self) -> bool:
        return bool(self._load().get("notifications_muted"))

    def mute_notifications(self) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        data = self._load()
        data["notifications_muted"] = True
        data["notifications_muted_at"] = now
        self._save(data)
        return now

    def unmute_notifications(self) -> None:
        data = self._load()
        data["notifications_muted"] = False
        data["notifications_muted_at"] = ""
        self._save(data)

    def get_notifications_muted_at(self) -> str:
        return self._load().get("notifications_muted_at", "")