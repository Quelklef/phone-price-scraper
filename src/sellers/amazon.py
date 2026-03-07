"""Amazon seller parser.

Design intent:
- Query Amazon search result pages with explicit condition facets.
- Re-validate listing cards via content smoke checks because Amazon can return
  adjacent/sponsored/off-target cards in the same result stream.
- Prefer search-card prices, but fall back to product-detail pages (PDP) when
  card markup omits or obfuscates the visible price.

Important idiosyncrasies:
- Search result HTML is noisy: sponsored cards, accessories, and near-models
  can appear despite a specific query.
- Title text is frequently fragmented in nested spans, and aria-label content
  is often the most complete title source.
- Price markup varies between full offscreen text and split whole/fraction
  nodes, so both extraction paths are required.
"""

import re
from urllib.parse import quote_plus, urljoin, urlsplit, urlunsplit

from lxml import html as lxml_html

import deps
from core import Condition, Model, Storage
from core import LogicExtractionError
from sellers.smoke_match import contains_multi_storage_listing, contains_other_model
from sellers.spec import SellerSpec


CONDITION_FILTER_EXPR = {
    # New
    Condition.BEST: "6503240011",
    # Renewed|Used
    Condition.GOOD: "16907722011%257C6503242011",
}


def build_search_url(model: Model, storage: Storage, condition: Condition, page: int):
    """Build canonical Amazon SERP URL for one model/condition/storage/page.

    Notes:
    - We intentionally keep Amazon's default ranking ("Featured") instead of
      forcing price sort; in practice, forced sort has caused relevant cards to
      disappear for some model+condition combinations.
    - Condition filtering is controlled by `rh` facet expression.
    """
    # Use default "Featured" ordering (omit sort param). Price sort can hide matches.
    storage_raw = str(storage)
    query = f"{model} {storage_raw}GB unlocked"
    rh_value = f"p_n_condition-type%3A{CONDITION_FILTER_EXPR[condition]}"
    params = {
        "k": quote_plus(query),
        "page": str(page),
    }
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://www.amazon.com/s?{query_string}&rh={rh_value}"


def _card_title_node(card):
    # From live Amazon markup: title is inside [data-cy='title-recipe'] and
    # rendered as <a ...><h2 ...><span>...</span></h2></a>.
    nodes = card.xpath(".//*[@data-cy='title-recipe']//h2")
    if nodes:
        return nodes[0]
    nodes = card.xpath(".//h2")
    return nodes[0] if nodes else None


def _card_title_text(card):
    # Prefer title-recipe anchor metadata/text because Amazon's h2 text can be
    # fragmented and sometimes yields only partial words.
    links = card.xpath(".//*[@data-cy='title-recipe']//a[@href]")
    for link in links:
        aria = (link.get("aria-label") or "").strip()
        if aria:
            return " ".join(aria.lower().split())
        text = " ".join(" ".join(link.itertext()).strip().split())
        if text:
            return text.lower()

    title = _card_title_node(card)
    if title is None:
        return ""
    return " ".join(" ".join(title.itertext()).strip().lower().split())


def _card_matches_filters(card, model: Model, storage: Storage):
    """Content-level guard for candidate search cards.

    Even with query parameters, Amazon often includes cards for neighboring
    models, bundles, or accessory SKUs. We only trust cards whose *title text*
    contains:
    - exact model phrase,
    - storage token,
    - "unlocked".

    We intentionally avoid condition words in title matching because many valid
    used/refurbished listings do not include a reliable condition token in the
    title itself; condition comes from search facets.
    """
    title_text = _card_title_text(card)
    if not title_text:
        return False

    # Reject cards that advertise multiple capacities ("128GB | 256GB ..."):
    # the shown card price is often a variant floor, not the requested storage.
    if contains_multi_storage_listing(title_text):
        return False

    # Keep the smoke-check scope narrow (title text only) to avoid
    # accidental matches from unrelated card metadata.
    if contains_other_model(title_text, model):
        return False

    model_tokens = str(model).lower().split()
    model_phrases = [model_tokens]
    # Amazon titles often omit the brand word even when query includes it
    # (for example, "Pixel 6a" instead of "Google Pixel 6a").
    # Accept both variants, still as exact phrase boundaries.
    if len(model_tokens) >= 2:
        model_phrases.append(model_tokens[1:])

    has_model_match = False
    for tokens in model_phrases:
        model_pattern = r"\b" + r"\s+".join(re.escape(part) for part in tokens) + r"\b"
        if re.search(model_pattern, title_text):
            has_model_match = True
            break
    if not has_model_match:
        return False

    digits = str(storage)
    if not re.search(rf"\b{digits}\s*g(?:b)?\b", title_text):
        return False

    # We only require "unlocked". Some valid listings include carrier names
    # (e.g. compatibility text) alongside "unlocked".
    if "unlocked" not in title_text:
        return False

    # Condition is enforced by Amazon facet query params; title text is not
    # reliable for all Used listings.
    return True


def _card_extract_price(card):
    return _extract_price_from_node(card)


def _extract_price_from_node(node):
    """Parse price from either card HTML or PDP HTML subtree.

    Extraction order:
    1) `.a-offscreen` text under `.a-price` (most robust when present),
    2) split whole/fraction nodes as fallback.

    Returns:
    - float price when parsable
    - None when no trustworthy number is found
    """
    # First preference is a parsed .a-offscreen price text.
    offscreen = node.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), ' a-price ')]"
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' a-offscreen ')]"
    )
    if offscreen:
        text = " ".join(offscreen[0].itertext()).strip()
        match = re.search(r"(\d[\d,]*(?:\.\d+)?)", text)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass

    # Fallback for split whole/fraction pricing markup.
    whole_nodes = node.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), ' a-price-whole ')]"
    )
    frac_nodes = node.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), ' a-price-fraction ')]"
    )
    for whole_node in whole_nodes:
        whole_text = re.sub(r"[^\d]", "", " ".join(whole_node.itertext()).strip())
        if not whole_text:
            continue
        frac_text = (
            "00"
            if not frac_nodes
            else re.sub(r"[^\d]", "", " ".join(frac_nodes[0].itertext()).strip())[:2].ljust(2, "0")
        )
        try:
            return float(f"{whole_text}.{frac_text}")
        except ValueError:
            continue
    return None


def _extract_product_page_price(product_html):
    """Read price from PDP HTML when search cards omit inline price."""
    with deps.timing.time_stage("html.parse"):
        doc = lxml_html.fromstring(product_html)

    with deps.timing.time_stage("listing.extract.pdp"):
        return _extract_price_from_node(doc)


def _card_extract_listing_url(card):
    """Return canonical ASIN URL for a result card.

    Canonicalization (`https://www.amazon.com/dp/<ASIN>`) reduces noise in
    known-price diffs caused by transient slugs/query/ref parameters.
    """
    link_nodes = card.xpath(
        ".//*[@data-cy='title-recipe']//a[@href]/@href"
        " | .//a[contains(@href, '/dp/')]/@href"
    )
    if not link_nodes:
        return None
    href = next((h for h in link_nodes if "/dp/" in h), link_nodes[0])
    if not href:
        return None

    absolute = urljoin("https://www.amazon.com", href)
    parts = urlsplit(absolute)
    # Canonicalize to ASIN-only URL and drop slug/query/ref path noise.
    match = re.search(r"/dp/([A-Z0-9]{10})(?:[/?]|$)", parts.path, re.IGNORECASE)
    if match:
        asin = match.group(1).upper()
        return f"https://www.amazon.com/dp/{asin}"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def extract_lowest_listing(html, model: Model, storage: Storage):
    """Extract lowest valid listing from one Amazon SERP page.

    This function is intentionally strict:
    - cards that pass smoke checks but fail URL/price extraction raise
      `LogicExtractionError` (signals parser drift),
    - cards that fail smoke checks are silently ignored.
    """
    with deps.timing.time_stage("html.parse"):
        doc = lxml_html.fromstring(html)
        cards = doc.xpath(
            "//div[@data-component-type='s-search-result'"
            " and normalize-space(@data-asin)!=''"
            " and contains(concat(' ', normalize-space(@class), ' '), ' s-result-item ')"
            " and contains(concat(' ', normalize-space(@class), ' '), ' s-asin ')]"
        )
    if not cards:
        return None, None

    with deps.timing.time_stage("listing.extract"):
        prices = []
        for card in cards:
            if not _card_matches_filters(card, model, storage):
                continue

            asin = card.get("data-asin", "").strip()
            listing_url = _card_extract_listing_url(card)
            if listing_url is None:
                raise LogicExtractionError(
                    f"Amazon matched card {asin or '<no-asin>'} missing listing URL."
                )
            price = _card_extract_price(card)
            if price is None:
                # Some matched result cards do not expose a usable inline price.
                # In that case, follow the product URL and read price from PDP.
                product_html = deps.http_cache.get(listing_url)
                price = _extract_product_page_price(product_html)
            if price is None:
                raise LogicExtractionError(
                    f"Amazon matched card {asin or '<no-asin>'} missing/invalid price after PDP fallback."
                )
            prices.append((price, listing_url))

        if not prices:
            return None, None
        return min(prices, key=lambda x: x[0])


def get_lowest_price(model: Model, condition: Condition, storage: Storage):
    """Public seller entrypoint.

    Policy:
    - scan first 3 pages,
    - keep the minimum price across all valid candidates,
    - return the query URLs used so known-prices can verify query intent.
    """
    query_urls = set()
    candidates = []
    for page in (1, 2, 3):
        url = build_search_url(model, storage, condition, page)
        query_urls.add(url)
        html = deps.http_cache.get(url)
        price, listing_url = extract_lowest_listing(html, model, storage)
        if price is None or listing_url is None:
            continue
        candidates.append((price, listing_url))

    if not candidates:
        return query_urls, None, None
    lowest_price, lowest_listing_url = min(candidates, key=lambda x: x[0])
    return query_urls, lowest_price, lowest_listing_url


SELLER = SellerSpec(
    key="amazon",
    get_lowest_price=get_lowest_price,
    condition_to_ui_words={
        Condition.BEST: ("New",),
        Condition.GOOD: ("Renewed", "Used"),
    },
)
