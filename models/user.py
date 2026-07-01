from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

from models.notification import DEFAULT_NOTIFICATION_PREFS


class UserRole(str, Enum):
    BOSS = "boss"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class Language(str, Enum):
    SWAHILI = "sw"
    ENGLISH = "en"
    KIRUNDI = "rn"


@dataclass
class EmployeePermissions:
    """Ruhusa za mfanyakazi — huwekwa na Manager."""

    can_view_products: bool = True
    can_sell: bool = True
    can_record_sales: bool = True
    can_view_sales_history: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EmployeePermissions":
        return cls(**{k: data.get(k, getattr(cls(), k)) for k in cls.__dataclass_fields__})


@dataclass
class User:
    id: str
    username: str
    password: str
    role: UserRole
    full_name: str
    shop_id: Optional[str] = None
    salary: float = 0.0
    permissions: EmployeePermissions = field(default_factory=EmployeePermissions)
    active: bool = True
    warnings: int = 0
    phone: str = ""
    email: str = ""
    bio: str = ""
    profile_picture: str = ""
    whatsapp: str = ""
    facebook: str = ""
    tiktok: str = ""
    language: str = "sw"
    notification_prefs: dict[str, bool] = field(
        default_factory=lambda: dict(DEFAULT_NOTIFICATION_PREFS)
    )
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "password": self.password,
            "role": self.role.value,
            "full_name": self.full_name,
            "shop_id": self.shop_id,
            "salary": self.salary,
            "permissions": self.permissions.to_dict(),
            "active": self.active,
            "warnings": self.warnings,
            "phone": self.phone,
            "email": self.email,
            "bio": self.bio,
            "profile_picture": self.profile_picture,
            "whatsapp": self.whatsapp,
            "facebook": self.facebook,
            "tiktok": self.tiktok,
            "language": self.language,
            "notification_prefs": self.notification_prefs,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            id=data["id"],
            username=data["username"],
            password=data["password"],
            role=UserRole(data["role"]),
            full_name=data["full_name"],
            shop_id=data.get("shop_id"),
            salary=data.get("salary", 0.0),
            permissions=EmployeePermissions.from_dict(data.get("permissions", {})),
            active=data.get("active", True),
            warnings=data.get("warnings", 0),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            bio=data.get("bio", ""),
            profile_picture=data.get("profile_picture", ""),
            whatsapp=data.get("whatsapp", ""),
            facebook=data.get("facebook", ""),
            tiktok=data.get("tiktok", ""),
            language=data.get("language", "sw"),
            notification_prefs={
                **DEFAULT_NOTIFICATION_PREFS,
                **data.get("notification_prefs", {}),
            },
            created_at=data.get("created_at", ""),
        )

    def is_boss(self) -> bool:
        return self.role == UserRole.BOSS

    def is_manager(self) -> bool:
        return self.role == UserRole.MANAGER

    def is_employee(self) -> bool:
        return self.role == UserRole.EMPLOYEE

    @property
    def has_profile_picture(self) -> bool:
        return bool(self.profile_picture)