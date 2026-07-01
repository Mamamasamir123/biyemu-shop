from dataclasses import dataclass


@dataclass
class PromoStatusCard:
    id: str
    name: str
    image: str
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "image": self.image,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PromoStatusCard":
        card_id = data.get("id") or str(data.get("slot", ""))
        return cls(
            id=str(card_id),
            name=data.get("name", ""),
            image=data.get("image", ""),
            updated_at=data.get("updated_at", data.get("created_at", "")),
        )