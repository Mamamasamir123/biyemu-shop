import json
import os
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class JsonStorage:
    """Hifadhi data kwenye faili za JSON."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, name: str) -> Path:
        return self.data_dir / f"{name}.json"

    def load_list(self, name: str, from_dict: Callable[[dict], T]) -> list[T]:
        path = self._file_path(name)
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [from_dict(item) for item in data]

    def save_list(self, name: str, items: list[Any]) -> None:
        path = self._file_path(name)
        data = [item.to_dict() if hasattr(item, "to_dict") else item for item in items]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_dict(self, name: str) -> dict:
        path = self._file_path(name)
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_dict(self, name: str, data: dict) -> None:
        path = self._file_path(name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def exists(self, name: str) -> bool:
        return self._file_path(name).exists()