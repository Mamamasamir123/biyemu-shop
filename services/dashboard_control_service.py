import uuid
from datetime import datetime
from typing import Optional

from models.dashboard_reset_request import DashboardResetRequest, DashboardResetStatus
from models.sale import Sale
from models.user import User, UserRole
from storage.json_storage import JsonStorage

ROLE_SECTIONS: dict[str, list[str]] = {
    UserRole.EMPLOYEE.value: [
        "my_sales",
        "cash_held",
        "cash_pending",
        "cash_confirmed",
    ],
    UserRole.MANAGER.value: [
        "products",
        "staff",
        "revenue",
        "cash_shop_available",
    ],
    UserRole.BOSS.value: [
        "capital",
        "revenue",
        "profit",
        "staff",
        "approvals",
        "net_profit",
    ],
}

# Mpangilio wa skrini ya dashibodi — kama mtumiaji anavyoiona
DASHBOARD_DISPLAY_ORDER: dict[str, list[str]] = {
    UserRole.EMPLOYEE.value: [
        "cash_held",
        "cash_pending",
        "cash_confirmed",
        "my_sales",
    ],
    UserRole.MANAGER.value: [
        "products",
        "staff",
        "revenue",
        "cash_shop_available",
    ],
    UserRole.BOSS.value: [
        "capital",
        "revenue",
        "profit",
        "staff",
        "approvals",
        "net_profit",
    ],
}

SECTION_ICONS: dict[str, str] = {
    "cash_held": "💵",
    "cash_pending": "⏳",
    "cash_confirmed": "✅",
    "capital": "💼",
    "revenue": "💰",
    "profit": "📈",
}


class DashboardControlService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def _load(self) -> dict:
        return self.storage.load_dict("dashboard_controls")

    def _save(self, data: dict) -> None:
        self.storage.save_dict("dashboard_controls", data)

    def sections_for_role(self, role: str) -> list[str]:
        return list(ROLE_SECTIONS.get(role, []))

    def display_order_for_role(self, role: str) -> list[str]:
        return list(DASHBOARD_DISPLAY_ORDER.get(role, []))

    def is_valid_section(self, user: User, section: str) -> bool:
        return section in self.sections_for_role(user.role.value)

    def get_period_start(self, user_id: str, section: str) -> str:
        return self._load().get(user_id, {}).get(section, "")

    def get_user_resets(self, user_id: str) -> dict[str, str]:
        return dict(self._load().get(user_id, {}))

    def reset_section(self, user_id: str, section: str) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        data = self._load()
        user_data = data.setdefault(user_id, {})
        user_data[section] = now
        self._save(data)
        return now

    @staticmethod
    def filter_sales(sales: list[Sale], period_start: str) -> list[Sale]:
        if not period_start:
            return sales
        return [s for s in sales if s.date >= period_start]

    @staticmethod
    def filter_by_created_at(items: list, period_start: str) -> list:
        if not period_start:
            return items
        return [
            i
            for i in items
            if getattr(i, "created_at", "") and i.created_at >= period_start
        ]

    def _get_requests(self) -> list[DashboardResetRequest]:
        return self.storage.load_list(
            "dashboard_reset_requests", DashboardResetRequest.from_dict
        )

    def _save_requests(self, items: list[DashboardResetRequest]) -> None:
        self.storage.save_list("dashboard_reset_requests", items)

    def has_pending_request(self, target_user_id: str, section: str) -> bool:
        return any(
            r.target_user_id == target_user_id
            and r.section == section
            and r.status == DashboardResetStatus.PENDING
            for r in self._get_requests()
        )

    def get_pending_for_user(self, user_id: str) -> list[DashboardResetRequest]:
        return sorted(
            [
                r
                for r in self._get_requests()
                if r.target_user_id == user_id
                and r.status == DashboardResetStatus.PENDING
            ],
            key=lambda r: r.created_at,
            reverse=True,
        )

    def get_by_id(self, request_id: str) -> Optional[DashboardResetRequest]:
        return next((r for r in self._get_requests() if r.id == request_id), None)

    def create_reset_request(
        self,
        *,
        target: User,
        section: str,
        boss: User,
    ) -> DashboardResetRequest:
        if not boss.is_boss():
            raise ValueError("boss_only")
        if target.is_boss():
            raise ValueError("cannot_target_boss")
        if section not in self.sections_for_role(target.role.value):
            raise ValueError("invalid_section")
        if self.has_pending_request(target.id, section):
            raise ValueError("already_pending")

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        req = DashboardResetRequest(
            id=str(uuid.uuid4())[:8],
            target_user_id=target.id,
            target_user_name=target.full_name,
            target_role=target.role.value,
            shop_id=target.shop_id or "",
            section=section,
            requested_by=boss.id,
            requester_name=boss.full_name,
            created_at=now,
        )
        items = self._get_requests()
        items.append(req)
        self._save_requests(items)
        return req

    def respond_request(
        self,
        request_id: str,
        user_id: str,
        *,
        approve: bool,
        note: str = "",
    ) -> DashboardResetRequest:
        items = self._get_requests()
        for i, req in enumerate(items):
            if req.id != request_id:
                continue
            if req.target_user_id != user_id:
                raise ValueError("not_target")
            if req.status != DashboardResetStatus.PENDING:
                raise ValueError("not_pending")
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            if approve:
                self.reset_section(req.target_user_id, req.section)
                items[i].status = DashboardResetStatus.APPROVED
            else:
                items[i].status = DashboardResetStatus.REJECTED
            items[i].responded_at = now
            items[i].response_note = note.strip()
            self._save_requests(items)
            return items[i]
        raise ValueError("not_found")