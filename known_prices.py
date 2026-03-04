import json
from pathlib import Path

from core import Condition, Model, Storage, normalize_model_name

# Partial expected best-deal checks across all sources.
# IMPORTANT: Do not change known prices without explicit user confirmation.
# Stored in JSON for easier editing and non-code diffs.
_KNOWN_PRICES_PATH = Path(__file__).resolve().parent / "data" / "known-prices.json"
KNOWN_PRICES_PATH = _KNOWN_PRICES_PATH
KnownPriceKey = tuple[str, Model, Storage, Condition]
KnownPriceValue = tuple[frozenset[str], float | None]


def _legacy_model_name_to_display_name(name):
    if not isinstance(name, str):
        raise ValueError(f"Invalid model name in known-prices.json: {name!r}")
    if name.startswith("PIXEL_"):
        suffix = name.removeprefix("PIXEL_").lower().replace("_", " ")
        return f"Pixel {suffix}"
    return name


def _normalize_model(raw_model):
    model = normalize_model_name(_legacy_model_name_to_display_name(raw_model))
    if not model:
        raise ValueError(f"Invalid empty model in known-prices.json: {raw_model!r}")
    return model


def _normalize_storage_gb(raw_storage):
    if isinstance(raw_storage, int):
        return raw_storage
    if isinstance(raw_storage, str):
        text = raw_storage.strip().lower()
        if text.startswith("gb_"):
            text = text.removeprefix("gb_")
        if text.endswith("gb"):
            text = text[:-2]
        if text.isdigit():
            return int(text)
    raise ValueError(f"Invalid storage in known-prices.json: {raw_storage!r}")


def _normalize_condition(raw_condition):
    if isinstance(raw_condition, str):
        if raw_condition in Condition.__members__:
            return Condition[raw_condition]
        for condition in Condition:
            if raw_condition.lower() == condition.value:
                return condition
    raise ValueError(f"Invalid condition in known-prices.json: {raw_condition!r}")


def _key_for_row(row):
    return (
        row["seller"],
        _normalize_model(row["model"]),
        _normalize_storage_gb(row["storage"]),
        _normalize_condition(row["condition"]),
    )


def _normalize_checked_urls(raw_urls, key):
    if not isinstance(raw_urls, list) or not raw_urls:
        raise ValueError(f"Invalid urls_checked for known price key {key}: {raw_urls!r}")

    urls = frozenset(
        u.strip() for u in raw_urls
        if isinstance(u, str) and u.strip()
    )
    if not urls:
        raise ValueError(f"urls_checked contains no valid URL values for key {key}.")
    return urls


def _normalize_computed_price(raw_price, key):
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return float(raw_price)
    raise ValueError(f"Invalid computed_price for known price key {key}: {raw_price!r}")


def _normalize_verified_at(raw_verified_at, key):
    if raw_verified_at is None:
        return None
    if isinstance(raw_verified_at, str) and raw_verified_at.strip():
        return raw_verified_at.strip()
    raise ValueError(f"Invalid verified_at for known price key {key}: {raw_verified_at!r}")


def _load_known_prices():
    if not _KNOWN_PRICES_PATH.exists():
        # Allow cold-start runs when data dir/cache is reset or moved.
        return {}

    rows = json.loads(_KNOWN_PRICES_PATH.read_text(encoding="utf-8"))
    prices: dict[KnownPriceKey, KnownPriceValue] = {}
    for row in rows:
        key = _key_for_row(row)
        if key in prices:
            raise ValueError(f"Duplicate known price key: {key}")
        urls = _normalize_checked_urls(row.get("urls_checked"), key)
        _normalize_verified_at(row.get("verified_at"), key)
        prices[key] = (urls, _normalize_computed_price(row.get("computed_price"), key))
    return prices


def load_known_price_rows():
    if not KNOWN_PRICES_PATH.exists():
        return []
    rows = json.loads(KNOWN_PRICES_PATH.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Known prices file must be a list: {KNOWN_PRICES_PATH}")
    return rows


def save_known_price_rows(rows):
    KNOWN_PRICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    KNOWN_PRICES_PATH.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


# Key: (seller, model, storage, condition)
# Value: (checked_query_urls, best_price)
KNOWN_PRICES: dict[KnownPriceKey, KnownPriceValue] = _load_known_prices()
