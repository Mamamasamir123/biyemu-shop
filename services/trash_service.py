import uuid
from datetime import datetime
from typing import Optional

from models.trash import TrashItem
from models.product import Product
from models.user import User
from storage.json_storage import JsonStorage


class TrashService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def get_all(self, shop_id: Optional[str] = None, item_type: Optional[str] = None) -> list[TrashItem]:
        items = self.storage.load_list("trash", TrashItem.from_dict)
        if shop_id:
            items = [i for i in items if i.shop_id == shop_id]
        if item_type:
            items = [i for i in items if i.item_type == item_type]
        return sorted(items, key=lambda i: i.deleted_at, reverse=True)

    def archive_product(
        self,
        product: Product,
        deleted_by: str,
        deleted_by_name: str,
        reason: str = "",
    ) -> TrashItem:
        item = TrashItem(
            id=str(uuid.uuid4())[:8],
            item_type="product",
            data=product.to_dict(),
            shop_id=product.shop_id,
            deleted_by=deleted_by,
            deleted_by_name=deleted_by_name,
            deleted_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            reason=reason,
        )
        items = self.storage.load_list("trash", TrashItem.from_dict)
        items.append(item)
        self.storage.save_list("trash", items)
        return item

    def archive_user(
        self,
        user: User,
        deleted_by: str,
        deleted_by_name: str,
        reason: str = "",
    ) -> TrashItem:
        item = TrashItem(
            id=str(uuid.uuid4())[:8],
            item_type="user",
            data=user.to_dict(),
            shop_id=user.shop_id or "",
            deleted_by=deleted_by,
            deleted_by_name=deleted_by_name,
            deleted_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            reason=reason,
        )
        items = self.storage.load_list("trash", TrashItem.from_dict)
        items.append(item)
        self.storage.save_list("trash", items)
        return item

    def get_by_id(self, item_id: str) -> Optional[TrashItem]:
        for item in self.storage.load_list("trash", TrashItem.from_dict):
            if item.id == item_id:
                return item
        return None

    def delete_permanently(self, item_id: str) -> TrashItem:
        items = self.storage.load_list("trash", TrashItem.from_dict)
        for i, item in enumerate(items):
            if item.id == item_id:
                removed = items.pop(i)
                self.storage.save_list("trash", items)
                return removed
        raise ValueError("Kipengele hakipatikani kwenye Takataka.")