"""BackMarket seller parser.

This seller parser is intentionally different from others because BackMarket is
heavily app-driven and variant state is encoded in Nuxt payloads.

High-level flow:
1) Load model root page (`/p/google-...`) and parse `__NUXT_DATA__`.
2) Select condition variant(s) matching requested quality bucket.
3) Open each selected condition context URL.
4) In that context, locate requested storage variant and read price from the
   storage picker HTML.

Why this split exists:
- Variant URL metadata (slug/productId) comes from Nuxt payload.
- Price visibility is most reliable in storage picker HTML under the condition
  context, not always directly in Nuxt item fields.
"""

import json
import re
from urllib.parse import urlencode, urlsplit, urlunsplit

import deps
from core import Condition, LogicExtractionError, Model, Storage, normalize_model_name
from lxml import html as lxml_html
import requests
from sellers.spec import SellerSpec

_CONDITION_GROUP_LABEL = "Condition"
_STORAGE_GROUP_LABEL = "Storage (GB)"
_BACKMARKET_MODEL_SLUGS = {
    # Google Pixel family
    normalize_model_name("Pixel 6a"): "google-pixel-6a",
    normalize_model_name("Pixel 6"): "google-pixel-6",
    normalize_model_name("Pixel 6 Pro"): "google-pixel-6-pro",
    normalize_model_name("Pixel 7a"): "google-pixel-7a",
    normalize_model_name("Pixel 7"): "google-pixel-7",
    normalize_model_name("Pixel 7 Pro"): "google-pixel-7-pro",
    normalize_model_name("Pixel Tablet"): "google-pixel-tablet",
    normalize_model_name("Pixel Fold"): "google-pixel-fold",
    normalize_model_name("Pixel 8a"): "google-pixel-8a",
    normalize_model_name("Pixel 8"): "google-pixel-8",
    normalize_model_name("Pixel 8 Pro"): "google-pixel-8-pro",
    normalize_model_name("Pixel 9a"): "google-pixel-9a",
    normalize_model_name("Pixel 9"): "google-pixel-9",
    normalize_model_name("Pixel 9 Pro"): "google-pixel-9-pro",
    normalize_model_name("Pixel 9 Pro XL"): "google-pixel-9-pro-xl",
    normalize_model_name("Pixel 9 Pro Fold"): "google-pixel-9-pro-fold",
    normalize_model_name("Pixel 10"): "google-pixel-10",
    normalize_model_name("Pixel 10 Pro"): "google-pixel-10-pro",
    normalize_model_name("Pixel 10 Pro XL"): "google-pixel-10-pro-xl",
    normalize_model_name("Pixel 10 Pro Fold"): "google-pixel-10-pro-fold",
    # Apple iPhone family
    normalize_model_name("iPhone 12"): "apple-iphone-12",
    normalize_model_name("iPhone 13"): "apple-iphone-13",
    normalize_model_name("iPhone 14"): "apple-iphone-14",
    normalize_model_name("iPhone 14 Plus"): "apple-iphone-14-plus",
    normalize_model_name("iPhone 14 Pro"): "apple-iphone-14-pro",
    normalize_model_name("iPhone 14 Pro Max"): "apple-iphone-14-pro-max",
    normalize_model_name("iPhone 15"): "apple-iphone-15",
    normalize_model_name("iPhone 15 Plus"): "apple-iphone-15-plus",
    normalize_model_name("iPhone 15 Pro"): "apple-iphone-15-pro",
    normalize_model_name("iPhone 15 Pro Max"): "apple-iphone-15-pro-max",
    normalize_model_name("iPhone 16"): "apple-iphone-16",
    normalize_model_name("iPhone 16 Plus"): "apple-iphone-16-plus",
    normalize_model_name("iPhone 16 Pro"): "apple-iphone-16-pro",
    normalize_model_name("iPhone 16 Pro Max"): "apple-iphone-16-pro-max",
    normalize_model_name("iPhone 16e"): "apple-iphone-16e",
    normalize_model_name("iPhone Se (2022)"): "apple-iphone-se-2022",
    # Samsung Galaxy family
    normalize_model_name("Galaxy S22"): "samsung-galaxy-s22",
    normalize_model_name("Galaxy S22 Plus"): "samsung-galaxy-s22-plus",
    normalize_model_name("Galaxy S22 Ultra"): "samsung-galaxy-s22-ultra",
    normalize_model_name("Galaxy S23"): "samsung-galaxy-s23",
    normalize_model_name("Galaxy S23 Plus"): "samsung-galaxy-s23-plus",
    normalize_model_name("Galaxy S23 Ultra"): "samsung-galaxy-s23-ultra",
    normalize_model_name("Galaxy S24"): "samsung-galaxy-s24",
    normalize_model_name("Galaxy S24 Plus"): "samsung-galaxy-s24-plus",
    normalize_model_name("Galaxy S24 Ultra"): "samsung-galaxy-s24-ultra",
    normalize_model_name("Galaxy Z Flip5"): "samsung-galaxy-z-flip-5",
    normalize_model_name("Galaxy Z Fold5"): "samsung-galaxy-z-fold-5",
}


def _model_slug(model: Model):
    """Map model name to BackMarket product slug suffix."""
    slug = _BACKMARKET_MODEL_SLUGS.get(model)
    if slug is None:
        raise LogicExtractionError(
            f"BackMarket does not have a configured model slug for '{model}'. "
            "Either add it to _BACKMARKET_MODEL_SLUGS or exclude backmarket via --search-sellers."
        )
    return slug


def _storage_label(storage: Storage):
    """Format storage label as rendered in BackMarket picker UI."""
    return f"{storage} GB"


def build_product_url(model: Model):
    """Build BackMarket model root URL."""
    return f"https://www.backmarket.com/en-us/p/{_model_slug(model)}"


def _load_nuxt_array(html):
    # Avoid full HTML DOM parsing; pull Nuxt payload script directly.
    match = re.search(
        r"<script[^>]*id=[\"']__NUXT_DATA__[\"'][^>]*>(.*?)</script>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return None
    raw = match.group(1).strip()
    if not raw:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def _resolve_once(nuxt_arr, value):
    """Resolve one Nuxt indirection step.

    Nuxt data may encode values as integer indexes into the top-level array.
    """
    if isinstance(value, int) and 0 <= value < len(nuxt_arr):
        return nuxt_arr[value]
    return value


def _find_picker_groups(nuxt_arr):
    """Find pickerGroups array within Nuxt payload."""
    for raw in nuxt_arr:
        item = _resolve_once(nuxt_arr, raw)
        if not isinstance(item, dict) or "pickerGroups" not in item:
            continue
        groups = _resolve_once(nuxt_arr, item.get("pickerGroups"))
        if isinstance(groups, list):
            return groups
    return []


def _iter_picker_items(nuxt_arr):
    """Yield `(group_label, item_refs)` for picker groups."""
    groups = _find_picker_groups(nuxt_arr)
    for group_ref in groups:
        group = _resolve_once(nuxt_arr, group_ref)
        if not isinstance(group, dict):
            continue
        label = _resolve_once(nuxt_arr, group.get("label"))
        items = _resolve_once(nuxt_arr, group.get("items"))
        if not isinstance(label, str) or not isinstance(items, list):
            continue
        yield label, items


def _extract_picker_item_url(nuxt_arr, item):
    """Build concrete variant URL from picker item payload."""
    slug = _resolve_once(nuxt_arr, item.get("slug"))
    product_id = _resolve_once(nuxt_arr, item.get("productId"))
    if not isinstance(slug, str) or not slug:
        return None
    if not isinstance(product_id, str) or not product_id:
        return None
    return f"https://www.backmarket.com/en-us/p/{slug}/{product_id}"


def _canonicalize_listing_url(url):
    """Normalize listing URL for stable known-price comparisons.

    We mask the model slug segment under `/p/` with `x` to avoid noisy diffs
    from slug wording changes while preserving product identity (`product_id`).
    """
    parts = urlsplit(url)
    path_parts = parts.path.split("/")
    try:
        p_idx = path_parts.index("p")
        if p_idx + 1 < len(path_parts):
            path_parts[p_idx + 1] = "x"
    except ValueError:
        pass
    return urlunsplit((parts.scheme, parts.netloc, "/".join(path_parts), "", ""))


def _extract_storage_price_from_storage_picker(condition_html, storage_label):
    """Extract target storage price from condition page storage picker HTML.

    We read from rendered picker list because this has proven more stable than
    relying only on Nuxt item price fields for all condition/storage contexts.
    """
    with deps.timing.time_stage("html.parse"):
        doc = lxml_html.fromstring(condition_html)

    storage_lists = doc.xpath("//ul[@aria-labelledby='heading-storage']")
    if not storage_lists:
        return None
    storage_list = storage_lists[0]
    storage_label_pattern = re.compile(rf"\b{re.escape(storage_label)}\b", flags=re.IGNORECASE)

    for li in storage_list.xpath("./li"):
        text = " ".join(" ".join(li.itertext()).split())
        if not storage_label_pattern.search(text):
            continue
        if "sold out" in text.lower():
            return None
        match = re.search(r"\$([0-9,]+(?:\.[0-9]{2})?)", text)
        if match is None:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _condition_query_tag(nuxt_arr, item):
    """Get condition tag used in condition-context URL query (`l=<tag>`)."""
    sorting_key = _resolve_once(nuxt_arr, item.get("sortingKey"))
    if isinstance(sorting_key, int):
        return sorting_key

    tracking_value = _resolve_once(nuxt_arr, item.get("trackingValue"))
    if isinstance(tracking_value, str) and tracking_value.isdigit():
        return int(tracking_value)
    return None


def _build_condition_url(base_url, tag):
    """Build condition-context URL used by BackMarket variant navigation."""
    query = urlencode(
        {
            "l": tag,
            "variantClicked": "true",
            "pickerClicked": "true",
        }
    )
    return f"{base_url}?{query}"


def _pick_item_by_label(nuxt_arr, group_label, wanted_label):
    """Find first picker item by group label + item label text."""
    for label, item_refs in _iter_picker_items(nuxt_arr):
        if label != group_label:
            continue
        for item_ref in item_refs:
            item = _resolve_once(nuxt_arr, item_ref)
            if not isinstance(item, dict):
                continue
            item_label = _resolve_once(nuxt_arr, item.get("label"))
            if item_label == wanted_label:
                return item
    return None


def _pick_available_item_by_label(nuxt_arr, group_label, wanted_label):
    """Find picker item and ensure it is available/acquirable."""
    item = _pick_item_by_label(nuxt_arr, group_label, wanted_label)
    if item is None:
        return None
    if not _is_picker_item_available(nuxt_arr, item):
        return None
    return item


def _is_picker_item_available(nuxt_arr, item):
    """Interpret BackMarket availability booleans conservatively."""
    available = _resolve_once(nuxt_arr, item.get("available"))
    acquirable = _resolve_once(nuxt_arr, item.get("acquirable"))
    return available is not False and acquirable is not False


def _selected_condition_label(nuxt_arr):
    """Read currently selected condition label from condition context payload."""
    for label, item_refs in _iter_picker_items(nuxt_arr):
        if label != _CONDITION_GROUP_LABEL:
            continue
        for item_ref in item_refs:
            item = _resolve_once(nuxt_arr, item_ref)
            if not isinstance(item, dict):
                continue
            selected = _resolve_once(nuxt_arr, item.get("selected"))
            if selected is True:
                value = _resolve_once(nuxt_arr, item.get("label"))
                return value if isinstance(value, str) else None
    return None


def _extract_listing_from_condition_context(condition_html, condition_label, storage: Storage):
    """Resolve one condition context into `(price, listing_url)` for storage.

    Returns `(None, None)` when:
    - payload cannot be parsed,
    - selected condition does not match expected condition,
    - requested storage is unavailable/missing,
    - price is missing/unparsable.
    """
    with deps.timing.time_stage("html.parse"):
        condition_nuxt = _load_nuxt_array(condition_html)
    if condition_nuxt is None:
        return None, None

    with deps.timing.time_stage("listing.extract.condition_context"):
        # Smoke-check the page state matches requested condition; otherwise our
        # URL traversal is wrong and results are untrustworthy.
        selected_condition = _selected_condition_label(condition_nuxt)
        if selected_condition is not None and selected_condition != condition_label:
            return None, None

        storage_label = _storage_label(storage)
        storage_item = _pick_available_item_by_label(condition_nuxt, _STORAGE_GROUP_LABEL, storage_label)
        if storage_item is None:
            return None, None

        storage_url = _extract_picker_item_url(condition_nuxt, storage_item)
        if storage_url is None or "unlocked" not in storage_url.lower():
            return None, None

        # Storage prices are read from the condition page's storage picker HTML.
        price = _extract_storage_price_from_storage_picker(condition_html, storage_label)
        if price is None:
            return None, None
        return price, _canonicalize_listing_url(storage_url)


def get_lowest_price(model: Model, condition: Condition, storage: Storage):
    """Public seller entrypoint for BackMarket."""
    root_url = build_product_url(model)
    try:
        root_html = deps.http_cache.get(root_url)
    except requests.HTTPError as e:
        if getattr(getattr(e, "response", None), "status_code", None) == 404:
            return {root_url}, None, None
        raise
    with deps.timing.time_stage("html.parse"):
        root_nuxt = _load_nuxt_array(root_html)
    if root_nuxt is None:
        return {root_url}, None, None

    # Condition-first flow: lock condition page first, validate it, then read
    # storage pricing from that condition page's storage picker HTML.
    prices = []
    with deps.timing.time_stage("listing.scan.condition"):
        # Iterate all labels that map to requested quality bucket and keep the
        # minimum valid candidate among them.
        for condition_label in SELLER.condition_to_ui_words[condition]:
            condition_item = _pick_available_item_by_label(root_nuxt, _CONDITION_GROUP_LABEL, condition_label)
            if condition_item is None:
                continue

            condition_base_url = _extract_picker_item_url(root_nuxt, condition_item)
            if condition_base_url is None or "unlocked" not in condition_base_url.lower():
                raise LogicExtractionError("BackMarket condition option missing valid unlocked URL.")
            condition_tag = _condition_query_tag(root_nuxt, condition_item)
            if condition_tag is None:
                raise LogicExtractionError("BackMarket condition option missing condition query tag.")

            condition_url = _build_condition_url(condition_base_url, condition_tag)
            condition_html = deps.http_cache.get(condition_url)

            price, listing_url = _extract_listing_from_condition_context(
                condition_html,
                condition_label,
                storage,
            )
            if price is None or listing_url is None:
                continue
            prices.append((price, listing_url))

    if not prices:
        return {root_url}, None, None
    best_price, listing_url = min(prices, key=lambda x: x[0])
    return {root_url}, best_price, listing_url


SELLER = SellerSpec(
    key="backmarket",
    get_lowest_price=get_lowest_price,
    condition_to_ui_words={
        Condition.BEST: ("Premium", "Excellent"),
        Condition.GOOD: ("Good",),
    },
)
