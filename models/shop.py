from dataclasses import dataclass


@dataclass
class Shop:
    id: str
    name: str
    shop_type: str
    location: str = ""
    logo: str = ""
    cover_image: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "shop_type": self.shop_type,
            "location": self.location,
            "logo": self.logo,
            "cover_image": self.cover_image,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Shop":
        return cls(
            id=data["id"],
            name=data["name"],
            shop_type=data["shop_type"],
            location=data.get("location", ""),
            logo=data.get("logo", ""),
            cover_image=data.get("cover_image", ""),
            description=data.get("description", ""),
        )

    @property
    def has_logo(self) -> bool:
        return bool(self.logo)

    @property
    def has_cover(self) -> bool:
        return bool(self.cover_image)