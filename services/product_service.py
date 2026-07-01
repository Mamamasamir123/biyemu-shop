import uuid
from datetime import datetime
from typing import Optional

from models.product import Product
from storage.json_storage import JsonStorage


class ProductService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def get_all(self, shop_id: Optional[str] = None) -> list[Product]:
        products = self.storage.load_list("products", Product.from_dict)
        if shop_id:
            return [p for p in products if p.shop_id == shop_id]
        return products

    def get_by_id(self, product_id: str) -> Optional[Product]:
        return next((p for p in self.get_all() if p.id == product_id), None)

    def add_product(
        self,
        name: str,
        price: float,
        quantity: int,
        shop_id: str,
        cost_price: float = 0.0,
        category: str = "",
        image: str = "",
    ) -> Product:
        product = Product(
            id=str(uuid.uuid4())[:8],
            name=name,
            price=price,
            quantity=quantity,
            shop_id=shop_id,
            cost_price=cost_price,
            category=category,
            image=image,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        products = self.get_all()
        products.append(product)
        self.storage.save_list("products", products)
        return product

    def update_product(self, product_id: str, **kwargs) -> Product:
        products = self.get_all()
        for i, product in enumerate(products):
            if product.id == product_id:
                for key, value in kwargs.items():
                    if hasattr(product, key) and value is not None:
                        setattr(products[i], key, value)
                self.storage.save_list("products", products)
                return products[i]
        raise ValueError("Bidhaa haijapatikana.")

    def delete_product(self, product_id: str) -> None:
        products = self.get_all()
        new_products = [p for p in products if p.id != product_id]
        if len(new_products) == len(products):
            raise ValueError("Bidhaa haijapatikana.")
        self.storage.save_list("products", new_products)

    def reduce_stock(self, product_id: str, quantity: int) -> Product:
        product = self.get_by_id(product_id)
        if not product:
            raise ValueError("Bidhaa haijapatikana.")
        if product.quantity < quantity:
            raise ValueError(f"Stock haitoshi. Ipo tu {product.quantity} vipande.")
        return self.update_product(product_id, quantity=product.quantity - quantity)