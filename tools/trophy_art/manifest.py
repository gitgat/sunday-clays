"""manifest.yaml → generation targets: one per art_key x metal (metal None for one-offs)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

METALS = ("bronze", "silver", "gold", "platinum", "diamond")


class ManifestError(ValueError):
    """The manifest is malformed."""


@dataclass(frozen=True)
class Target:
    art_key: str
    metal: str | None
    prompt: str
    negative: str
    model: str
    seeds: tuple[int, ...]
    size: int
    steps: int | None = None
    cfg: float | None = None
    sampler: str | None = None
    scheduler: str | None = None

    @property
    def stem(self) -> str:
        return self.art_key if self.metal is None else f"{self.art_key}-{self.metal}"


def split_stem(stem: str) -> tuple[str, str | None]:
    art_key, _, metal = stem.rpartition("-")
    return (art_key, metal) if art_key and metal in METALS else (stem, None)


def _opt[T](entry: dict[str, Any], defaults: dict[str, Any], key: str, cast: Callable[[Any], T]) -> T | None:
    value = entry.get(key, defaults.get(key))
    return None if value is None else cast(value)


def load_manifest(path: Path) -> list[Target]:
    doc: dict[str, Any] = yaml.safe_load(path.read_text())
    style = str(doc["style"])
    defaults: dict[str, Any] = doc["defaults"]
    phrases: dict[str, str] = doc["metal_phrases"]
    targets: list[Target] = []
    seen: set[str] = set()
    for entry in doc["trophies"]:
        art_key = str(entry["art_key"])
        metals: list[str | None] = [str(m) for m in entry.get("metals", [])] or [None]
        for metal in metals:
            if metal is not None and metal not in METALS:
                raise ManifestError(f"{art_key}: unknown metal {metal!r}")
            target = Target(
                art_key=art_key,
                metal=metal,
                prompt=(
                    f"{entry.get('style', style)}, {phrases['one_off' if metal is None else metal]}, {entry['prompt']}"
                ),
                negative=str(entry.get("negative", defaults["negative"])),
                model=str(entry.get("model", defaults["model"])),
                seeds=tuple(int(s) for s in entry.get("seeds", defaults["seeds"])),
                size=int(entry.get("size", defaults["size"])),
                steps=_opt(entry, defaults, "steps", int),
                cfg=_opt(entry, defaults, "cfg", float),
                sampler=_opt(entry, defaults, "sampler", str),
                scheduler=_opt(entry, defaults, "scheduler", str),
            )
            if target.stem in seen:
                raise ManifestError(f"duplicate target {target.stem}")
            seen.add(target.stem)
            targets.append(target)
    return targets
