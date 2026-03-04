"""Swappa seller parser.

Design intent:
- Query Swappa listing pages with explicit filters in query params.
- Verify Swappa actually applied those filters by inspecting the rendered
  filter form state before trusting any cards.

Why this matters:
- Swappa may ignore unsupported filter combinations (for example storage values
  with no inventory) and still return broad results. Without form-state checks,
  those broad results can be mistaken as valid hits for the requested quad.
"""

import re
from lxml import html as lxml_html
import requests

import deps
from core import Condition, Model, Storage, normalize_model_name
from core import LogicExtractionError
from sellers.spec import SellerSpec

_FILTER_FORM_XPATH = "//*[@id='filter_form']"
_CARD_XPATH = "//*[contains(concat(' ', normalize-space(@class), ' '), ' xui_card ')]"

_SWAPPA_MODEL_SLUGS = {
    # Google Pixel family
    normalize_model_name("Pixel 6"): "google-pixel-6",
    normalize_model_name("Pixel 6a"): "google-pixel-6a",
    normalize_model_name("Pixel 6 Pro"): "google-pixel-6-pro",
    normalize_model_name("Pixel 7"): "google-pixel-7",
    normalize_model_name("Pixel 7a"): "google-pixel-7a",
    normalize_model_name("Pixel 7 Pro"): "google-pixel-7-pro",
    normalize_model_name("Pixel Fold"): "google-pixel-fold",
    normalize_model_name("Pixel Tablet"): "google-pixel-tablet",
    normalize_model_name("Pixel 8"): "google-pixel-8",
    normalize_model_name("Pixel 8a"): "google-pixel-8a",
    normalize_model_name("Pixel 8 Pro"): "google-pixel-8-pro",
    normalize_model_name("Pixel 9"): "google-pixel-9",
    normalize_model_name("Pixel 9a"): "google-pixel-9a",
    normalize_model_name("Pixel 9 Pro"): "google-pixel-9-pro",
    normalize_model_name("Pixel 9 Pro XL"): "google-pixel-9-pro-xl",
    normalize_model_name("Pixel 9 Pro Fold"): "google-pixel-9-pro-fold",
    normalize_model_name("Pixel 10"): "google-pixel-10",
    normalize_model_name("Pixel 10 Pro"): "google-pixel-10-pro",
    normalize_model_name("Pixel 10 Pro XL"): "google-pixel-10-pro-xl",
    normalize_model_name("Pixel 10 Pro Fold"): "google-pixel-10-pro-fold",
    # Apple iPhone family
    normalize_model_name("iPhone 11"): "apple-iphone-11",
    normalize_model_name("iPhone 11 Pro"): "apple-iphone-11-pro",
    normalize_model_name("iPhone 11 Pro Max"): "apple-iphone-11-pro-max",
    normalize_model_name("iPhone 12"): "apple-iphone-12",
    normalize_model_name("iPhone 12 Mini"): "apple-iphone-12-mini",
    normalize_model_name("iPhone 12 Pro"): "apple-iphone-12-pro",
    normalize_model_name("iPhone 12 Pro Max"): "apple-iphone-12-pro-max",
    normalize_model_name("iPhone 13"): "apple-iphone-13",
    normalize_model_name("iPhone 13 Mini"): "apple-iphone-13-mini",
    normalize_model_name("iPhone 13 Pro"): "apple-iphone-13-pro",
    normalize_model_name("iPhone 13 Pro Max"): "apple-iphone-13-pro-max",
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
    normalize_model_name("iPhone SE (2022)"): "apple-iphone-se-3rd-gen-2022",
    # Samsung Galaxy S / Note / Z
    normalize_model_name("Galaxy S20"): "samsung-galaxy-s20",
    normalize_model_name("Galaxy S20 Plus"): "samsung-galaxy-s20-plus",
    normalize_model_name("Galaxy S20 Ultra"): "samsung-galaxy-s20-ultra",
    normalize_model_name("Galaxy S20 FE"): "samsung-galaxy-s20-fe",
    normalize_model_name("Galaxy S21"): "samsung-galaxy-s21",
    normalize_model_name("Galaxy S21 Plus"): "samsung-galaxy-s21-plus",
    normalize_model_name("Galaxy S21 Ultra"): "samsung-galaxy-s21-ultra",
    normalize_model_name("Galaxy S21 FE"): "samsung-galaxy-s21-fe",
    normalize_model_name("Galaxy S22"): "samsung-galaxy-s22",
    normalize_model_name("Galaxy S22 Plus"): "samsung-galaxy-s22-plus",
    normalize_model_name("Galaxy S22 Ultra"): "samsung-galaxy-s22-ultra",
    normalize_model_name("Galaxy S23"): "samsung-galaxy-s23",
    normalize_model_name("Galaxy S23 Plus"): "samsung-galaxy-s23-plus",
    normalize_model_name("Galaxy S23 Ultra"): "samsung-galaxy-s23-ultra",
    normalize_model_name("Galaxy S24"): "samsung-galaxy-s24",
    normalize_model_name("Galaxy S24 Plus"): "samsung-galaxy-s24-plus",
    normalize_model_name("Galaxy S24 Ultra"): "samsung-galaxy-s24-ultra",
    normalize_model_name("Galaxy S25"): "samsung-galaxy-s25",
    normalize_model_name("Galaxy S25 Plus"): "samsung-galaxy-s25-plus",
    normalize_model_name("Galaxy S25 Ultra"): "samsung-galaxy-s25-ultra",
    normalize_model_name("Galaxy Note 20"): "samsung-galaxy-note-20",
    normalize_model_name("Galaxy Note 20 Ultra"): "samsung-galaxy-note-20-ultra",
    normalize_model_name("Galaxy Note 10"): "samsung-galaxy-note-10",
    normalize_model_name("Galaxy Note 10 Plus"): "samsung-galaxy-note-10-plus",
    normalize_model_name("Galaxy Note 9"): "samsung-galaxy-note-9",
    normalize_model_name("Galaxy Z Flip5"): "samsung-galaxy-z-flip5",
    normalize_model_name("Galaxy Z Fold5"): "samsung-galaxy-z-fold5",
}


def _swappa_model_slug_or_fail(model: Model):
    slug = _SWAPPA_MODEL_SLUGS.get(model)
    if slug is None:
        raise LogicExtractionError(
            f"Swappa does not have a configured model slug for '{model}'. "
            "Either add it to _SWAPPA_MODEL_SLUGS or exclude swappa via --search-sellers."
        )
    return slug


def build_listing_url(model: Model, condition: str, storage: Storage):
    """Build Swappa listing query URL for one condition variant."""
    model_slug = _swappa_model_slug_or_fail(model)
    return (
        f"https://swappa.com/listings/{model_slug}"
        f"?condition={condition}&carrier=unlocked"
        f"&storage={storage}&sort=price_low"
    )


def _extract_listing_id(card):
    """Extract listing ID from Swappa card subtree.

    Expected DOM pattern is `xui_card_body_<LISTING_ID>`.
    """
    # Swappa collapse body id like "xui_card_body_LACI60829".
    for node in card.xpath(".//*[@id]"):
        match = re.match(r"xui_card_body_(\w+)", node.get("id", ""))
        if match:
            return match.group(1)
    return None


def _extract_card_price(card):
    """Extract numeric card price from `.price` subtree text."""
    price_nodes = card.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), ' price ')]"
    )
    if not price_nodes:
        return None
    text = " ".join(price_nodes[0].itertext()).strip()
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _selected_filter_value(doc, field_name):
    # Read server-rendered selected option from #filter_form descendants.
    selected = doc.xpath(
        f"{_FILTER_FORM_XPATH}//select[@name='{field_name}']/option[@selected][1]/@value"
    )
    if selected:
        return selected[0]

    # Fallback to first option when "selected" is omitted.
    first = doc.xpath(
        f"{_FILTER_FORM_XPATH}//select[@name='{field_name}']/option[1]/@value"
    )
    return first[0] if first else None


def _filter_form_matches_query(doc, requested_condition, requested_storage):
    """Verify Swappa actually applied our query params in #filter_form.

    Why this guard exists:
    - Swappa sometimes ignores unsupported filter combinations (notably storage)
      and still returns broad listings instead of an empty result set.
    - If we trust those cards, we can record bogus "lowest prices" for quads that
      should have no listings.

    Policy:
    - We only trust the listing cards when #filter_form shows the same selected
      values we requested for condition/carrier/storage/sort.
    - If any selected value differs, treat that page as no-results for this query.
    """
    expected = {
        "condition": requested_condition,
        "carrier": "unlocked",
        "storage": requested_storage,
        "sort": "price_low",
    }
    for name, expected_value in expected.items():
        actual_value = _selected_filter_value(doc, name)
        if actual_value != expected_value:
            return False
    return True


def get_lowest_price(model: Model, condition: Condition, storage: Storage):
    """Public seller entrypoint.

    For `Condition.BEST`, Swappa is queried with multiple acceptable condition
    buckets (`new`, `mint`). We aggregate all valid candidates and take the
    minimum.
    """
    query_urls = set()
    candidates = []
    for swappa_condition in SELLER.condition_to_ui_words[condition]:
        url = build_listing_url(model, swappa_condition, storage)
        query_urls.add(url)
        try:
            html = deps.http_cache.get(url)
        except requests.HTTPError as e:
            # Treat missing listing pages as a clean no-results state.
            if getattr(getattr(e, "response", None), "status_code", None) == 404:
                continue
            raise
        with deps.timing.time_stage("html.parse"):
            doc = lxml_html.fromstring(html)
            if not _filter_form_matches_query(doc, swappa_condition, storage):
                continue
        with deps.timing.time_stage("listing.extract"):
            cards = doc.xpath(_CARD_XPATH)
            for card in cards:
                listing_id = _extract_listing_id(card)
                price = _extract_card_price(card)
                if listing_id is None:
                    raise LogicExtractionError(
                        "Swappa matched card found but missing listing id from xui_card_body_<id>."
                    )
                if price is None:
                    raise LogicExtractionError(
                        f"Swappa matched card {listing_id} found but missing/invalid .price value."
                    )
                listing_url = f"https://swappa.com/listing/view/{listing_id}"
                candidates.append((price, listing_url))

    if not candidates:
        return query_urls, None, None
    lowest_price, lowest_listing_url = min(candidates, key=lambda x: x[0])
    return query_urls, lowest_price, lowest_listing_url


SELLER = SellerSpec(
    key="swappa",
    get_lowest_price=get_lowest_price,
    condition_to_ui_words={
        Condition.BEST: ("new", "mint"),
        Condition.GOOD: ("good",),
    },
)
