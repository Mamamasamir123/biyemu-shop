import uuid
from typing import Optional

from models.shop import Shop
from storage.json_storage import JsonStorage


class ShopService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def get_all(self) -> list[Shop]:
        return self.storage.load_list("shops", Shop.from_dict)

    def get_by_id(self, shop_id: str) -> Optional[Shop]:
        return next((s for s in self.get_all() if s.id == shop_id), None)

    def add_shop(self, name: str, shop_type: str, location: str = "") -> Shop:
        if not name.startswith("BiyeMu"):
            name = f"BiyeMu {name}"

        shop = Shop(
            id=str(uuid.uuid4())[:8],
            name=name,
            shop_type=shop_type,
            location=location,
        )
        shops = self.get_all()
        shops.append(shop)
        self.storage.save_list("shops", shops)
        return shop

    def update_shop(
        self,
        shop_id: str,
        *,
        name: str | None = None,
        shop_type: str | None = None,
        location: str | None = None,
        description: str | None = None,
        logo: str | None = None,
        cover_image: str | None = None,
    ) -> Shop:
        shops = self.get_all()
        for i, shop in enumerate(shops):
            if shop.id == shop_id:
                if name is not None:
                    shops[i].name = name if name.startswith("BiyeMu") else f"BiyeMu {name}"
                if shop_type is not None:
                    shops[i].shop_type = shop_type
                if location is not None:
                    shops[i].location = location
                if description is not None:
                    shops[i].description = description
                if logo is not None:
                    shops[i].logo = logo
                if cover_image is not None:
                    shops[i].cover_image = cover_image
                self.storage.save_list("shops", shops)
                return shops[i]
        raise ValueError("Duka halijapatikana.")