from dataclasses import dataclass


@dataclass
class Product:
    id: str
    name: str
    price: float
    quantity: int
    shop_id: str
    cost_price: float = 0.0
    category: str = ""
    image: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "quantity": self.quantity,
            "shop_id": self.shop_id,
            "cost_price": self.cost_price,
            "category": self.category,
            "image": self.image,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        return cls(
            id=data["id"],
            name=data["name"],
            price=data["price"],
            quantity=data["quantity"],
            shop_id=data["shop_id"],
            cost_price=data.get("cost_price", 0.0),
            category=data.get("category", ""),
            image=data.get("image", ""),
            created_at=data.get("created_at", ""),
        )

    @property
    def stock_value(self) -> float:
        return self.price * self.quantity

    @property
    def capital_value(self) -> float:
        return self.cost_price * self.quantity

    @property
    def potential_profit(self) -> float:
        return (self.price - self.cost_price) * self.quantity