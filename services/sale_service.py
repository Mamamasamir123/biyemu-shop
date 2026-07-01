import uuid
from datetime import datetime
from typing import Optional

from models.sale import Sale
from storage.json_storage import JsonStorage


class SaleService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def get_all(self, shop_id: Optional[str] = None) -> list[Sale]:
        sales = self.storage.load_list("sales", Sale.from_dict)
        if shop_id:
            return [s for s in sales if s.shop_id == shop_id]
        return sales

    def record_sale(
        self,
        product_id: str,
        product_name: str,
        shop_id: str,
        employee_id: str,
        employee_name: str,
        quantity: int,
        unit_price: float,
        cost_price: float,
    ) -> Sale:
        total = unit_price * quantity
        sale = Sale(
            id=str(uuid.uuid4())[:8],
            product_id=product_id,
            product_name=product_name,
            shop_id=shop_id,
            employee_id=employee_id,
            employee_name=employee_name,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total,
            cost_price=cost_price,
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            cash_status="held",
        )
        sales = self.get_all()
        sales.append(sale)
        self.storage.save_list("sales", sales)
        return sale

    def mark_sales_status(
        self, sale_ids: list[str], status: str, remittance_id: str = ""
    ) -> None:
        id_set = set(sale_ids)
        sales = self.get_all()
        for i, sale in enumerate(sales):
            if sale.id in id_set:
                sales[i].cash_status = status
                if remittance_id:
                    sales[i].remittance_id = remittance_id
        self.storage.save_list("sales", sales)

    def revert_sales_remittance(
        self, sale_ids: list[str], status: str
    ) -> None:
        id_set = set(sale_ids)
        sales = self.get_all()
        for i, sale in enumerate(sales):
            if sale.id in id_set:
                sales[i].cash_status = status
                sales[i].remittance_id = ""
        self.storage.save_list("sales", sales)

    def get_by_ids(self, sale_ids: list[str]) -> list[Sale]:
        id_set = set(sale_ids)
        return [s for s in self.get_all() if s.id in id_set]

    def get_by_id(self, sale_id: str) -> Optional[Sale]:
        return next((s for s in self.get_all() if s.id == sale_id), None)

    def delete_sale(self, sale_id: str) -> Optional[Sale]:
        sales = self.get_all()
        for i, sale in enumerate(sales):
            if sale.id == sale_id:
                removed = sales.pop(i)
                self.storage.save_list("sales", sales)
                return removed
        return None