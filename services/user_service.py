import uuid
from datetime import datetime
from typing import Optional

from models.user import User, UserRole, EmployeePermissions
from storage.json_storage import JsonStorage


class UserService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def get_all(self) -> list[User]:
        return self.storage.load_list("users", User.from_dict)

    def get_by_id(self, user_id: str) -> Optional[User]:
        return next((u for u in self.get_all() if u.id == user_id), None)

    def get_by_shop(self, shop_id: str) -> list[User]:
        return [u for u in self.get_all() if u.shop_id == shop_id]

    def get_managers(self) -> list[User]:
        return [u for u in self.get_all() if u.role == UserRole.MANAGER]

    def get_employees(self, shop_id: Optional[str] = None) -> list[User]:
        employees = [u for u in self.get_all() if u.role == UserRole.EMPLOYEE]
        if shop_id:
            return [e for e in employees if e.shop_id == shop_id]
        return employees

    def username_exists(self, username: str) -> bool:
        return any(u.username.lower() == username.lower() for u in self.get_all())

    def add_user(
        self,
        username: str,
        password: str,
        role: UserRole,
        full_name: str,
        shop_id: Optional[str] = None,
        salary: float = 0.0,
    ) -> User:
        if self.username_exists(username):
            raise ValueError(f"Jina la mtumiaji '{username}' tayari lipo.")

        user = User(
            id=str(uuid.uuid4())[:8],
            username=username,
            password=password,
            role=role,
            full_name=full_name,
            shop_id=shop_id,
            salary=salary,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        users = self.get_all()
        users.append(user)
        self.storage.save_list("users", users)
        return user

    def update_salary(self, user_id: str, salary: float) -> User:
        users = self.get_all()
        for i, user in enumerate(users):
            if user.id == user_id:
                users[i].salary = salary
                self.storage.save_list("users", users)
                return users[i]
        raise ValueError("Mtumiaji hajapatikana.")

    def update_permissions(self, user_id: str, permissions: EmployeePermissions) -> User:
        users = self.get_all()
        for i, user in enumerate(users):
            if user.id == user_id:
                users[i].permissions = permissions
                self.storage.save_list("users", users)
                return users[i]
        raise ValueError("Mtumiaji hajapatikana.")

    def deactivate_user(self, user_id: str) -> User:
        users = self.get_all()
        for i, user in enumerate(users):
            if user.id == user_id:
                users[i].active = False
                self.storage.save_list("users", users)
                return users[i]
        raise ValueError("Mtumiaji hajapatikana.")

    def activate_user(self, user_id: str) -> User:
        users = self.get_all()
        for i, user in enumerate(users):
            if user.id == user_id:
                users[i].active = True
                self.storage.save_list("users", users)
                return users[i]
        raise ValueError("Mtumiaji hajapatikana.")

    def add_warning(self, user_id: str) -> User:
        users = self.get_all()
        for i, user in enumerate(users):
            if user.id == user_id:
                users[i].warnings += 1
                self.storage.save_list("users", users)
                return users[i]
        raise ValueError("Mtumiaji hajapatikana.")

    def clear_warning(self, user_id: str) -> User:
        users = self.get_all()
        for i, user in enumerate(users):
            if user.id == user_id:
                if users[i].warnings > 0:
                    users[i].warnings -= 1
                self.storage.save_list("users", users)
                return users[i]
        raise ValueError("Mtumiaji hajapatikana.")

    def update_profile(
        self,
        user_id: str,
        *,
        full_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        bio: str | None = None,
        whatsapp: str | None = None,
        facebook: str | None = None,
        tiktok: str | None = None,
        language: str | None = None,
        profile_picture: str | None = None,
    ) -> User:
        users = self.get_all()
        for i, user in enumerate(users):
            if user.id == user_id:
                if full_name is not None:
                    users[i].full_name = full_name
                if phone is not None:
                    users[i].phone = phone
                if email is not None:
                    users[i].email = email
                if bio is not None:
                    users[i].bio = bio
                if whatsapp is not None:
                    users[i].whatsapp = whatsapp
                if facebook is not None:
                    users[i].facebook = facebook
                if tiktok is not None:
                    users[i].tiktok = tiktok
                if language is not None:
                    users[i].language = language
                if profile_picture is not None:
                    users[i].profile_picture = profile_picture
                self.storage.save_list("users", users)
                return users[i]
        raise ValueError("Mtumiaji hajapatikana.")

    def remove_user(self, user_id: str) -> User:
        users = self.get_all()
        for i, user in enumerate(users):
            if user.id == user_id:
                removed = users.pop(i)
                self.storage.save_list("users", users)
                return removed
        raise ValueError("Mtumiaji hajapatikana.")

    def update_notification_prefs(
        self, user_id: str, prefs: dict[str, bool]
    ) -> User:
        users = self.get_all()
        for i, user in enumerate(users):
            if user.id == user_id:
                users[i].notification_prefs = prefs
                self.storage.save_list("users", users)
                return users[i]
        raise ValueError("Mtumiaji hajapatikana.")

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        users = self.get_all()
        for i, user in enumerate(users):
            if user.id == user_id:
                if user.password != old_password:
                    return False
                users[i].password = new_password
                self.storage.save_list("users", users)
                return True
        raise ValueError("Mtumiaji hajapatikana.")