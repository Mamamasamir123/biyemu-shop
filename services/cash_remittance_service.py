import uuid
from datetime import datetime, timedelta
from typing import Optional

from models.cash_remittance import CashRemittance, RemittanceStatus
from models.sale import Sale
from models.user import User, UserRole
from storage.json_storage import JsonStorage

CASH_PERIODS = ("all", "today", "week", "month")
REMITTANCE_FROM_EMPLOYEE = "from_employee"
REMITTANCE_FROM_MANAGER = "from_manager"


class CashRemittanceService:
    def __init__(self, storage: JsonStorage, sale_service, user_service):
        self.storage = storage
        self.sale_service = sale_service
        self.user_service = user_service

    def get_all(self) -> list[CashRemittance]:
        return self.storage.load_list("cash_remittances", CashRemittance.from_dict)

    def get_by_id(self, remittance_id: str) -> Optional[CashRemittance]:
        return next((r for r in self.get_all() if r.id == remittance_id), None)

    def get_shop_manager(self, shop_id: str) -> Optional[User]:
        for user in self.user_service.get_by_shop(shop_id):
            if user.role == UserRole.MANAGER and user.active:
                return user
        return None

    def resolve_receiver(self, shop_id: str) -> tuple[str, str, str]:
        manager = self.get_shop_manager(shop_id)
        if manager:
            return manager.id, manager.full_name, UserRole.MANAGER.value
        bosses = [u for u in self.user_service.get_all() if u.role == UserRole.BOSS and u.active]
        if bosses:
            boss = bosses[0]
            return boss.id, boss.full_name, UserRole.BOSS.value
        raise ValueError("no_receiver")

    def resolve_boss_receiver(self) -> tuple[str, str, str]:
        bosses = [u for u in self.user_service.get_all() if u.role == UserRole.BOSS and u.active]
        if bosses:
            boss = bosses[0]
            return boss.id, boss.full_name, UserRole.BOSS.value
        raise ValueError("no_receiver")

    @staticmethod
    def _parse_sale_date(date_str: str) -> datetime:
        return datetime.strptime(date_str[:16], "%Y-%m-%d %H:%M")

    @classmethod
    def filter_by_period(cls, sales: list[Sale], period: str) -> list[Sale]:
        if period not in CASH_PERIODS or period == "all":
            return sorted(sales, key=lambda s: s.date, reverse=True)
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "today":
            cutoff = today_start
        elif period == "week":
            cutoff = today_start - timedelta(days=today_start.weekday())
        else:
            cutoff = today_start.replace(day=1)
        filtered = [s for s in sales if cls._parse_sale_date(s.date) >= cutoff]
        return sorted(filtered, key=lambda s: s.date, reverse=True)

    def get_held_sales(self, employee_id: str, period: str = "all") -> list[Sale]:
        held = [
            s
            for s in self.sale_service.get_all()
            if s.employee_id == employee_id and s.cash_status == "held"
        ]
        return self.filter_by_period(held, period)

    def get_held_total(self, employee_id: str) -> float:
        return sum(s.total_amount for s in self.get_held_sales(employee_id, "all"))

    def get_shop_manager_held_sales(self, shop_id: str, period: str = "all") -> list[Sale]:
        held = [
            s
            for s in self.sale_service.get_all(shop_id)
            if s.cash_status == "manager_held"
        ]
        return self.filter_by_period(held, period)

    def get_shop_manager_held_total(self, shop_id: str) -> float:
        return sum(s.total_amount for s in self.get_shop_manager_held_sales(shop_id, "all"))

    @staticmethod
    def select_sales_for_amount(sales: list[Sale], amount: float) -> list[Sale]:
        if amount <= 0:
            return []
        ordered = sorted(sales, key=lambda s: s.date)
        selected: list[Sale] = []
        total = 0.0
        for sale in ordered:
            if total + sale.total_amount <= amount + 0.01:
                selected.append(sale)
                total += sale.total_amount
            elif not selected:
                selected.append(sale)
                break
        return selected

    def _validate_sale_selection(self, employee_id: str, sale_ids: list[str]) -> list[Sale]:
        if not sale_ids:
            raise ValueError("no_selection")
        held_map = {s.id: s for s in self.get_held_sales(employee_id, "all")}
        selected = []
        for sale_id in sale_ids:
            sale = held_map.get(sale_id)
            if not sale:
                raise ValueError("invalid_sales")
            selected.append(sale)
        return selected

    def _validate_shop_sale_selection(self, shop_id: str, sale_ids: list[str]) -> list[Sale]:
        if not sale_ids:
            raise ValueError("no_selection")
        held_map = {s.id: s for s in self.get_shop_manager_held_sales(shop_id, "all")}
        selected = []
        for sale_id in sale_ids:
            sale = held_map.get(sale_id)
            if not sale:
                raise ValueError("invalid_sales")
            selected.append(sale)
        return selected

    def _persist_remittance(
        self,
        submitter: User,
        selected: list[Sale],
        note: str,
        receiver_id: str,
        receiver_name: str,
        receiver_role: str,
        remittance_kind: str,
        pending_status: str,
    ) -> CashRemittance:
        amount = sum(s.total_amount for s in selected)
        sale_ids = [s.id for s in selected]
        remittance = CashRemittance(
            id=str(uuid.uuid4())[:8],
            shop_id=submitter.shop_id,
            employee_id=submitter.id,
            employee_name=submitter.full_name,
            receiver_id=receiver_id,
            receiver_name=receiver_name,
            receiver_role=receiver_role,
            amount=amount,
            sale_ids=sale_ids,
            remittance_kind=remittance_kind,
            note=note,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        items = self.get_all()
        items.append(remittance)
        self.storage.save_list("cash_remittances", items)
        self.sale_service.mark_sales_status(sale_ids, pending_status, remittance.id)
        return remittance

    def create_remittance(
        self, employee: User, note: str = "", sale_ids: list[str] | None = None
    ) -> CashRemittance:
        if sale_ids:
            selected = self._validate_sale_selection(employee.id, sale_ids)
        else:
            selected = self.get_held_sales(employee.id, "all")
        if not selected:
            raise ValueError("no_held_sales")
        receiver_id, receiver_name, receiver_role = self.resolve_receiver(employee.shop_id)
        return self._persist_remittance(
            employee,
            selected,
            note,
            receiver_id,
            receiver_name,
            receiver_role,
            REMITTANCE_FROM_EMPLOYEE,
            "pending",
        )

    def create_remittance_from_amount(
        self, employee: User, amount: float, note: str = ""
    ) -> CashRemittance:
        if amount <= 0:
            raise ValueError("invalid_amount")
        held = self.get_held_sales(employee.id, "all")
        if not held:
            raise ValueError("no_held_sales")
        held_total = sum(s.total_amount for s in held)
        if amount > held_total + 0.01:
            raise ValueError("amount_exceeds_held")
        selected = self.select_sales_for_amount(held, amount)
        if not selected:
            raise ValueError("no_held_sales")
        receiver_id, receiver_name, receiver_role = self.resolve_receiver(employee.shop_id)
        return self._persist_remittance(
            employee,
            selected,
            note,
            receiver_id,
            receiver_name,
            receiver_role,
            REMITTANCE_FROM_EMPLOYEE,
            "pending",
        )

    def create_manager_remittance(
        self, manager: User, note: str = "", sale_ids: list[str] | None = None
    ) -> CashRemittance:
        if sale_ids:
            selected = self._validate_shop_sale_selection(manager.shop_id, sale_ids)
        else:
            selected = self.get_shop_manager_held_sales(manager.shop_id, "all")
        if not selected:
            raise ValueError("no_held_sales")
        receiver_id, receiver_name, receiver_role = self.resolve_boss_receiver()
        return self._persist_remittance(
            manager,
            selected,
            note,
            receiver_id,
            receiver_name,
            receiver_role,
            REMITTANCE_FROM_MANAGER,
            "boss_pending",
        )

    def create_manager_remittance_from_amount(
        self, manager: User, amount: float, note: str = ""
    ) -> CashRemittance:
        if amount <= 0:
            raise ValueError("invalid_amount")
        held = self.get_shop_manager_held_sales(manager.shop_id, "all")
        if not held:
            raise ValueError("no_held_sales")
        held_total = sum(s.total_amount for s in held)
        if amount > held_total + 0.01:
            raise ValueError("amount_exceeds_held")
        selected = self.select_sales_for_amount(held, amount)
        if not selected:
            raise ValueError("no_held_sales")
        receiver_id, receiver_name, receiver_role = self.resolve_boss_receiver()
        return self._persist_remittance(
            manager,
            selected,
            note,
            receiver_id,
            receiver_name,
            receiver_role,
            REMITTANCE_FROM_MANAGER,
            "boss_pending",
        )

    def get_pending_for_user(self, user: User) -> list[CashRemittance]:
        pending = [r for r in self.get_all() if r.status == RemittanceStatus.PENDING]
        if user.role == UserRole.BOSS:
            return [r for r in pending if r.receiver_role == UserRole.BOSS.value]
        if user.role == UserRole.MANAGER:
            return [
                r
                for r in pending
                if r.receiver_id == user.id and r.remittance_kind == REMITTANCE_FROM_EMPLOYEE
            ]
        return []

    def can_confirm(self, remittance: CashRemittance, user: User) -> bool:
        if remittance.status != RemittanceStatus.PENDING:
            return False
        if user.role == UserRole.BOSS:
            return remittance.receiver_role == UserRole.BOSS.value
        if user.role == UserRole.MANAGER:
            return (
                remittance.receiver_id == user.id
                and remittance.remittance_kind == REMITTANCE_FROM_EMPLOYEE
            )
        return False

    def reject(self, remittance_id: str, user: User, note: str = "") -> CashRemittance:
        remittance = self.get_by_id(remittance_id)
        if not remittance or not self.can_confirm(remittance, user):
            raise ValueError("not_found")
        if remittance.remittance_kind == REMITTANCE_FROM_MANAGER:
            revert_status = "manager_held"
        else:
            revert_status = "held"
        items = self.get_all()
        for i, item in enumerate(items):
            if item.id == remittance_id:
                items[i].status = RemittanceStatus.REJECTED
                items[i].confirmed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
                items[i].confirmed_by_id = user.id
                items[i].confirmed_by_name = user.full_name
                if note:
                    items[i].note = note
                self.storage.save_list("cash_remittances", items)
                self.sale_service.revert_sales_remittance(item.sale_ids, revert_status)
                return items[i]
        raise ValueError("not_found")

    def confirm(self, remittance_id: str, user: User, note: str = "") -> CashRemittance:
        remittance = self.get_by_id(remittance_id)
        if not remittance or not self.can_confirm(remittance, user):
            raise ValueError("not_found")
        if remittance.receiver_role == UserRole.MANAGER.value:
            target_status = "manager_held"
        else:
            target_status = "confirmed"
        items = self.get_all()
        for i, item in enumerate(items):
            if item.id == remittance_id:
                items[i].status = RemittanceStatus.CONFIRMED
                items[i].confirmed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
                items[i].confirmed_by_id = user.id
                items[i].confirmed_by_name = user.full_name
                if note:
                    items[i].note = note
                self.storage.save_list("cash_remittances", items)
                self.sale_service.mark_sales_status(item.sale_ids, target_status, item.id)
                return items[i]
        raise ValueError("not_found")

    def get_submitter_remittances(self, submitter_id: str) -> list[CashRemittance]:
        return sorted(
            [r for r in self.get_all() if r.employee_id == submitter_id],
            key=lambda r: r.created_at,
            reverse=True,
        )

    def get_employee_remittances(self, employee_id: str) -> list[CashRemittance]:
        return self.get_submitter_remittances(employee_id)

    def count_pending_for_user(self, user: User) -> int:
        return len(self.get_pending_for_user(user))