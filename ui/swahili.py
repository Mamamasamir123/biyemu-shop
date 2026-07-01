"""Tafsiri za maneno ya mfumo kwa Kiswahili."""

from models.user import UserRole
from models.approval import ApprovalType, ApprovalStatus


JUKUMU: dict[UserRole, str] = {
    UserRole.BOSS: "Mkuu (Admin)",
    UserRole.MANAGER: "Meneja",
    UserRole.EMPLOYEE: "Mfanyakazi",
}

AINA_OMBII: dict[ApprovalType, str] = {
    ApprovalType.ADD_PRODUCT: "Kuongeza bidhaa",
    ApprovalType.DELETE_PRODUCT: "Kufuta bidhaa",
    ApprovalType.DELETE_SALE: "Kufuta mauzo",
    ApprovalType.BULK_PRICE_CHANGE: "Kubadilisha bei kwa wingi",
}

HALI_OMBII: dict[ApprovalStatus, str] = {
    ApprovalStatus.PENDING: "Inasubiri",
    ApprovalStatus.APPROVED: "Imeidhinishwa",
    ApprovalStatus.REJECTED: "Imekataliwa",
    ApprovalStatus.CANCELLED: "Imesimamishwa",
}


def jukumu(role: UserRole | str) -> str:
    if isinstance(role, str):
        try:
            role = UserRole(role)
        except ValueError:
            return role
    return JUKUMU.get(role, role.value)


def aina_ombi(approval_type: ApprovalType | str) -> str:
    if isinstance(approval_type, str):
        try:
            approval_type = ApprovalType(approval_type)
        except ValueError:
            return approval_type
    return AINA_OMBII.get(approval_type, approval_type.value)


def hali_ombi(status: ApprovalStatus | str) -> str:
    if isinstance(status, str):
        try:
            status = ApprovalStatus(status)
        except ValueError:
            return status
    return HALI_OMBII.get(status, status.value)