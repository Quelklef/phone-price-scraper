from dataclasses import dataclass
from typing import Callable

from core import Condition, Model, Storage

ScrapeResult = tuple[set[str], float | None, str | None]


@dataclass(frozen=True)
class SellerSpec:
    """Unified seller contract consumed by analysis/verification flows."""

    key: str
    get_lowest_price: Callable[[Model, Condition, Storage], ScrapeResult]
    condition_to_ui_words: dict[Condition, tuple[str, ...]]
