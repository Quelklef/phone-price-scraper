"""eBay seller parser.

Design intent:
- Build a tightly filtered eBay search URL (model, storage, unlock status,
  condition buckets, buy-it-now only, low-price sorting).
- Apply secondary content smoke checks to each result card because eBay can
  still return loosely related items under broad search behavior.

Why the extra strictness:
- eBay search can surface cards with "read description"/"see description"
  placeholders where crucial attributes are not present in card text.
- Some cards include price ranges or variant groupings; parser normalizes these
  to a comparable lower-bound float where appropriate.
"""

from urllib.parse import quote, quote_plus, urlsplit, urlunsplit

from lxml import html as lxml_html
import re

import deps
from core import Condition
from core import LogicExtractionError
from sellers.spec import SellerSpec
from sellers.smoke_match import (
    normalize_text,
    passes_model_smoke_checks,
    storage_terms,
    text_matches,
)

CONDITION_TERMS = {
    Condition.BEST: "1000|1500|2010",  # 1000=new, 1500=open box, 2010=excellent
    Condition.GOOD: "2020|2030",       # 2020=very good, 2030=good
}


def build_search_url(model: str, condition: Condition, storage: int):
    """Build eBay search URL with encoded facet/query parameters.

    Notes on encoding:
    - Certain eBay facet keys/values require double-encoding to match current
      URL contract used by the site.
    - We keep this encoding style stable because small encoding shifts can
      silently change result sets.
    """
    storage_raw = str(storage)
    model_query = f"Google {model}"
    model_encoded = quote(quote(model_query, safe=""), safe="")
    status_encoded = quote(quote("Factory Unlocked", safe=""), safe="")

    params = {
        "_fsrp": "1",
        "_nkw": quote_plus(model_query),
        "Capacity": storage_raw,
        "Lock%2520Status": status_encoded,
        "LH_ItemCondition": CONDITION_TERMS[condition],
        "Model": model_encoded,
        "LH_BIN": "1",  # Buy It Now only.
        "_sop": "15",   # Sort by price low-to-high.
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://www.ebay.com/sch/i.html?{query}"


def _card_matches_filters(card, model: str, condition: Condition, storage: int):
    """Validate candidate result card text against expected quad.

    Checks include:
    - model smoke checks (reject near/superstring models),
    - condition terms,
    - storage tokens.

    We intentionally limit extraction scope to title/subtitle text to avoid
    false positives from unrelated metadata regions.
    """
    nodes = card.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), ' s-card__title ')"
        " or contains(concat(' ', normalize-space(@class), ' '), ' s-card__subtitle ')]"
    )
    if not nodes:
        return False

    # Smoke-check is intentionally constrained to title/subtitle only.
    haystack_text = " ".join(" ".join(node.itertext()).strip() for node in nodes)
    haystack = normalize_text(haystack_text)
    if "readdescription" in haystack or "seedescription" in haystack:
        return False
    if not passes_model_smoke_checks(haystack, model):
        return False
    return text_matches(
        haystack_text,
        model_terms=[str(model)],
        condition_terms=SELLER.condition_to_ui_words[condition],
        storage_term_values=storage_terms(storage),
        normalized_haystack=haystack,
    )


def _card_extract_price(card):
    """Parse card price, handling both fixed values and simple ranges."""
    tags = card.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), ' s-card__price ')]"
    )
    if not tags:
        return None

    text = " ".join(tags[0].itertext()).strip().lower()
    # eBay often renders ranges like "$120 to $150"; take the lower bound.
    if "to" in text:
        text = text.split("to", 1)[0]
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _card_extract_listing_url(card):
    """Return canonical listing URL without query/fragment noise."""
    hrefs = card.xpath(
        ".//a[contains(concat(' ', normalize-space(@class), ' '), ' s-card__link ')]/@href"
    )
    if not hrefs:
        return None
    href = hrefs[0]
    parts = urlsplit(href)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def extract_lowest_listing(html, model: str, condition: Condition, storage: int):
    """Extract lowest valid listing from one eBay search response.

    Important behavior:
    - "No exact matches found" answer blocks are treated as clean no-results.
    - If a *matched* card is missing required fields, we raise
      `LogicExtractionError` to signal parser drift instead of silently
      accepting degraded extraction.
    """
    with deps.timing.time_stage("html.parse"):
        doc = lxml_html.fromstring(html)

    # eBay sometimes returns a "No exact matches found" answer block
    # instead of listing cards; treat it as a valid no-results state.
    with deps.timing.time_stage("listing.extract"):
        if doc.xpath(
            "//*[contains(concat(' ', normalize-space(@class), ' '), ' srp-river-answer ')"
            " and contains(normalize-space(string(.)), 'No exact matches found')]"
        ):
            return None, None

        prices = []

    # Validate each result card against model/condition/storage text before
    # trusting its price. This adds a content-level guard in case query params
    # are ignored or partially applied for some models.
        cards = doc.xpath(
            "//*[contains(concat(' ', normalize-space(@class), ' '), ' s-card ')]"
        )
        for card in cards:
            if not _card_matches_filters(card, model, condition, storage):
                continue
            price = _card_extract_price(card)
            listing_url = _card_extract_listing_url(card)
            if price is None:
                raise LogicExtractionError(
                    "eBay matched card found but missing/invalid .s-card__price."
                )
            if listing_url is None:
                raise LogicExtractionError(
                    "eBay matched card found but missing .s-card__link href."
                )
            prices.append((price, listing_url))

        if not prices:
            return None, None
        return min(prices, key=lambda x: x[0])


def get_lowest_price(model: str, condition: Condition, storage: int):
    """Public seller entrypoint for eBay (single query URL)."""
    url = build_search_url(model, condition, storage)
    html = deps.http_cache.get(url)
    price, listing_url = extract_lowest_listing(html, model, condition, storage)
    return {url}, price, listing_url


SELLER = SellerSpec(
    key="ebay",
    get_lowest_price=get_lowest_price,
    condition_to_ui_words={
        Condition.BEST: ("new", "open box", "excellent"),
        Condition.GOOD: ("very good", "good"),
    },
)
