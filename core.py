from enum import StrEnum


class Condition(StrEnum):
    GOOD = "good"
    BEST = "best"


Model = str
Storage = int


def normalize_model_name(raw_model: str) -> Model:
    # Canonicalize spacing/casing so differently-cased or differently-spaced
    # user input resolves to the same model key.
    words = raw_model.strip().split()
    base = " ".join(words).title()
    lower = base.lower()
    if lower.startswith("pixel "):
        return f"Google {base}"
    return base


_RAW_KNOWN_MODELS: list[Model] = [
    "Pixel 6a",
    "Pixel 6",
    "Pixel 6 Pro",
    "Pixel 7a",
    "Pixel 7",
    "Pixel 7 Pro",
    "Pixel Tablet",
    "Pixel Fold",
    "Pixel 8a",
    "Pixel 8",
    "Pixel 8 Pro",
    "Pixel 9a",
    "Pixel 9",
    "Pixel 9 Pro",
    "Pixel 9 Pro XL",
    "Pixel 9 Pro Fold",
    "Pixel 10",
    "Pixel 10 Pro",
    "Pixel 10 Pro XL",
    "Pixel 10 Pro Fold",
]

KNOWN_MODELS: list[Model] = [normalize_model_name(model) for model in _RAW_KNOWN_MODELS]


class LogicExtractionError(RuntimeError):
    """Raised when seller selectors find cards but cannot extract required fields."""


class KnownPriceMismatchError(RuntimeError):
    """Raised when a known_prices expectation does not match computed output."""
