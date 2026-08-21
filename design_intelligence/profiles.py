from __future__ import annotations

import json
from importlib.resources import files

from .models import ProductProfile


def list_profiles() -> list[str]:
    base = files("design_intelligence").joinpath("data/product_profiles")
    return sorted(path.stem for path in base.iterdir() if path.suffix == ".json")


def load_profile(name: str) -> ProductProfile:
    base = files("design_intelligence").joinpath("data/product_profiles")
    path = base.joinpath(f"{name}.json")
    if not path.exists():
        available = ", ".join(list_profiles())
        raise ValueError(f"Unknown profile '{name}'. Available profiles: {available}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProductProfile(**data)
