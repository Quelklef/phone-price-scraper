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


class LogicExtractionError(RuntimeError):
    """Raised when seller selectors find cards but cannot extract required fields."""


class KnownPriceMismatchError(RuntimeError):
    """Raised when a known_prices expectation does not match computed output."""
