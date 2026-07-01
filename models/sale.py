from dataclasses import dataclass


@dataclass
class Sale:
    id: str
    product_id: str
    product_name: str
    shop_id: str
    employee_id: str
    employee_name: str
    quantity: int
    unit_price: float
    total_amount: float
    cost_price: float
    date: str
    cash_status: str = "held"
    remittance_id: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "shop_id": self.shop_id,
            "employee_id": self.employee_id,
            "employee_name": self.employee_name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total_amount": self.total_amount,
            "cost_price": self.cost_price,
            "date": self.date,
            "cash_status": self.cash_status,
            "remittance_id": self.remittance_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Sale":
        return cls(
            id=data["id"],
            product_id=data["product_id"],
            product_name=data["product_name"],
            shop_id=data["shop_id"],
            employee_id=data["employee_id"],
            employee_name=data["employee_name"],
            quantity=data["quantity"],
            unit_price=data["unit_price"],
            total_amount=data["total_amount"],
            cost_price=data.get("cost_price", 0.0),
            date=data["date"],
            cash_status=data.get("cash_status", "confirmed"),
            remittance_id=data.get("remittance_id", ""),
        )

    @property
    def profit(self) -> float:
        return self.total_amount - (self.cost_price * self.quantity)