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
from core import Condition, Model, Storage
from core import LogicExtractionError
from sellers.spec import SellerSpec

_FILTER_FORM_XPATH = "//*[@id='filter_form']"
_CARD_XPATH = "//*[contains(concat(' ', normalize-space(@class), ' '), ' xui_card ')]"


def to_kebab_case(model: Model):
    """Convert model display text to Swappa slug fragment."""
    # Model labels are "Pixel ..."; Swappa slug path already prefixes "google-pixel-".
    model_without_prefix = model.removeprefix("Pixel ")
    return model_without_prefix.lower().replace(" ", "-")


def build_listing_url(model: Model, condition: str, storage: Storage):
    """Build Swappa listing query URL for one condition variant."""
    model_slug = to_kebab_case(model)
    return (
        f"https://swappa.com/listings/google-pixel-{model_slug}"
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
