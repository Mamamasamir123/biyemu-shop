import json
import uuid
from datetime import datetime

from models.banner import PromoStatusCard
from storage.json_storage import JsonStorage


class BannerService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def _load_raw(self) -> list[dict]:
        path = self.storage.data_dir / "banners.json"
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _migrate_legacy(self, raw: list[dict]) -> list[dict]:
        if not raw:
            return []
        migrated = []
        for item in raw:
            row = dict(item)
            if not row.get("id"):
                row["id"] = str(uuid.uuid4())[:8]
            row.pop("slot", None)
            row.pop("active", None)
            row.pop("created_at", None)
            migrated.append(row)
        return migrated

    def _save(self, cards: list[PromoStatusCard]) -> None:
        self.storage.save_list("banners", cards)

    def get_all(self) -> list[PromoStatusCard]:
        raw = self._migrate_legacy(self._load_raw())
        return [PromoStatusCard.from_dict(item) for item in raw]

    def cleanup_empty_cards(self) -> None:
        raw = self._migrate_legacy(self._load_raw())
        cards = [PromoStatusCard.from_dict(item) for item in raw]
        kept = [c for c in cards if c.image or c.name.strip()]
        if len(kept) != len(cards):
            self._save(kept)

    def get_feed_cards(self) -> list[PromoStatusCard]:
        self.cleanup_empty_cards()
        return [card for card in self.get_all() if card.image]

    def get_admin_cards(self) -> list[PromoStatusCard]:
        self.cleanup_empty_cards()
        return self.get_all()

    def get_card(self, card_id: str) -> PromoStatusCard | None:
        for card in self.get_all():
            if card.id == card_id:
                return card
        return None

    def add_card(self) -> PromoStatusCard:
        cards = self.get_all()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        card = PromoStatusCard(
            id=str(uuid.uuid4())[:8],
            name="",
            image="",
            updated_at=now,
        )
        cards.append(card)
        self._save(cards)
        return card

    def update_card(
        self,
        card_id: str,
        *,
        name: str | None = None,
        image_filename: str | None = None,
    ) -> PromoStatusCard:
        cards = self.get_all()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        updated = None
        for card in cards:
            if card.id != card_id:
                continue
            if name is not None:
                card.name = name.strip()
            if image_filename:
                card.image = image_filename
            card.updated_at = now
            updated = card
            break
        if not updated:
            raise ValueError("not_found")
        self._save(cards)
        return updated

    def delete_card(self, card_id: str) -> bool:
        cards = self.get_all()
        new_cards = [c for c in cards if c.id != card_id]
        if len(new_cards) == len(cards):
            return False
        self._save(new_cards)
        return True