from dataclasses import dataclass
from typing import Optional

from models.sale import Sale
from models.user import UserRole
from services.sale_service import SaleService
from services.user_service import UserService
from services.product_service import ProductService


@dataclass
class FinanceReport:
    total_revenue: float
    total_cost: float
    total_profit: float
    total_salaries: float
    net_profit: float
    sales_count: int
    held_revenue: float = 0.0
    pending_revenue: float = 0.0
    manager_held_revenue: float = 0.0
    boss_pending_revenue: float = 0.0


@dataclass
class ShopDashboard:
    capital: float
    revenue: float
    profit: float
    sales_count: int
    units_sold: int
    products_count: int
    employees_count: int
    net_profit: float
    held_revenue: float = 0.0
    pending_revenue: float = 0.0
    manager_held_revenue: float = 0.0
    boss_pending_revenue: float = 0.0


@dataclass
class CompanyDashboard:
    shops_count: int
    total_capital: float
    total_revenue: float
    total_profit: float
    sales_count: int
    units_sold: int
    held_revenue: float = 0.0
    pending_revenue: float = 0.0


class FinanceService:
    def __init__(
        self,
        sale_service: SaleService,
        user_service: UserService,
        product_service: ProductService,
    ):
        self.sale_service = sale_service
        self.user_service = user_service
        self.product_service = product_service

    @staticmethod
    def _confirmed_sales(sales: list[Sale]) -> list[Sale]:
        return [s for s in sales if s.cash_status == "confirmed"]

    @staticmethod
    def _cash_totals(sales: list[Sale]) -> tuple[float, float, float, float]:
        held = sum(s.total_amount for s in sales if s.cash_status == "held")
        pending = sum(s.total_amount for s in sales if s.cash_status == "pending")
        manager_held = sum(s.total_amount for s in sales if s.cash_status == "manager_held")
        boss_pending = sum(s.total_amount for s in sales if s.cash_status == "boss_pending")
        return held, pending, manager_held, boss_pending

    def get_shop_capital(self, shop_id: str) -> float:
        products = self.product_service.get_all(shop_id)
        return sum(p.cost_price * p.quantity for p in products)

    def get_shop_dashboard(self, shop_id: str) -> ShopDashboard:
        products = self.product_service.get_all(shop_id)
        sales = self.sale_service.get_all(shop_id)
        report = self.get_shop_report(shop_id)
        employees = self.user_service.get_by_shop(shop_id)
        held, pending, manager_held, boss_pending = self._cash_totals(sales)
        return ShopDashboard(
            capital=sum(p.cost_price * p.quantity for p in products),
            revenue=report.total_revenue,
            profit=report.total_profit,
            sales_count=report.sales_count,
            units_sold=sum(s.quantity for s in sales),
            products_count=len(products),
            employees_count=len(employees),
            net_profit=report.net_profit,
            held_revenue=held,
            pending_revenue=pending,
            manager_held_revenue=manager_held,
            boss_pending_revenue=boss_pending,
        )

    def get_shop_report(self, shop_id: str) -> FinanceReport:
        sales = self.sale_service.get_all(shop_id)
        confirmed = self._confirmed_sales(sales)
        employees = self.user_service.get_by_shop(shop_id)
        salaries = sum(u.salary for u in employees if u.role == UserRole.EMPLOYEE)
        held, pending, manager_held, boss_pending = self._cash_totals(sales)

        revenue = sum(s.total_amount for s in confirmed)
        cost = sum(s.cost_price * s.quantity for s in confirmed)
        profit = sum(s.profit for s in confirmed)

        return FinanceReport(
            total_revenue=revenue,
            total_cost=cost,
            total_profit=profit,
            total_salaries=salaries,
            net_profit=profit - salaries,
            sales_count=len(confirmed),
            held_revenue=held,
            pending_revenue=pending,
            manager_held_revenue=manager_held,
            boss_pending_revenue=boss_pending,
        )

    def get_all_shops_report(self) -> dict[str, FinanceReport]:
        shops_reports = {}
        for shop_id in {s.shop_id for s in self.sale_service.get_all()}:
            shops_reports[shop_id] = self.get_shop_report(shop_id)
        return shops_reports

    def get_company_summary(self) -> FinanceReport:
        sales = self.sale_service.get_all()
        confirmed = self._confirmed_sales(sales)
        all_users = self.user_service.get_all()
        salaries = sum(
            u.salary for u in all_users if u.role in (UserRole.EMPLOYEE, UserRole.MANAGER)
        )
        held, pending, manager_held, boss_pending = self._cash_totals(sales)

        revenue = sum(s.total_amount for s in confirmed)
        cost = sum(s.cost_price * s.quantity for s in confirmed)
        profit = sum(s.profit for s in confirmed)

        return FinanceReport(
            total_revenue=revenue,
            total_cost=cost,
            total_profit=profit,
            total_salaries=salaries,
            net_profit=profit - salaries,
            sales_count=len(confirmed),
            held_revenue=held,
            pending_revenue=pending,
            manager_held_revenue=manager_held,
            boss_pending_revenue=boss_pending,
        )

    def get_company_dashboard(self, shops_count: int) -> CompanyDashboard:
        products = self.product_service.get_all()
        sales = self.sale_service.get_all()
        summary = self.get_company_summary()
        return CompanyDashboard(
            shops_count=shops_count,
            total_capital=sum(p.cost_price * p.quantity for p in products),
            total_revenue=summary.total_revenue,
            total_profit=summary.total_profit,
            sales_count=summary.sales_count,
            units_sold=sum(s.quantity for s in sales),
            held_revenue=summary.held_revenue,
            pending_revenue=summary.pending_revenue,
        )