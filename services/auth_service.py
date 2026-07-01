from typing import Optional

from models.user import User
from storage.json_storage import JsonStorage


class AuthService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def login(self, username: str, password: str) -> Optional[User]:
        users = self._get_users()
        for user in users:
            if (
                user.username.lower() == username.lower()
                and user.password == password
                and user.active
            ):
                return user
        return None

    def _get_users(self) -> list[User]:
        return self.storage.load_list("users", User.from_dict)