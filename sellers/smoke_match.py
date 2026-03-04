"""Shared smoke checks used by multiple marketplace seller parsers.

These checks are intentionally heuristic. The goal is to reject obvious
off-target listings while keeping behavior stable across seller DOM changes.
"""

import re

from core import Model, Storage

# Common cross-brand variant words. This is not exhaustive, but it covers most
# mainstream phone suffixes and gives us a brand-agnostic baseline.
_VARIANT_TOKENS = frozenset(
    {
        "a",      # Google Pixel A-series (e.g. 8a).
        "plus",   # Common larger-tier suffix (e.g. iPhone Plus, Galaxy Plus).
        "pro",    # Common premium-tier suffix across brands.
        "max",    # Max-tier suffix (often larger/better spec variant).
        "ultra",  # Top-tier suffix (common on Samsung/Xiaomi).
        "mini",   # Compact variant suffix.
        "lite",   # Lower-tier/lighter feature variant.
        "fe",     # Samsung "Fan Edition".
        "fold",   # Foldable-book style variant (Fold/Pro Fold).
        "flip",   # Clamshell foldable variant.
        "xl",     # Extra-large variant suffix.
        "se",     # Apple "Special Edition" style suffix.
        "t",      # OnePlus T refresh variant.
        "r",      # OnePlus R performance/value branch.
        "edge",   # Motorola/Samsung-style edge branded variant.
        "core",   # Core/entry-tier variant suffix.
        "neo",    # Neo refresh/sub-variant suffix.
    }
)
_SEPARATOR_RE = re.compile(r"(?:-|/|\||,|&|\band\b)", flags=re.IGNORECASE)
# Detect storage mentions like "128GB", "256 gb", or "64g".
# We intentionally require at least 2 digits so "5g" network text is not
# misread as storage. We also avoid `\b...\b` boundaries because some listings
# use Unicode separators (for example "512GB丨256GB") that can break word-boundary
# assumptions; numeric lookarounds are more robust here.
_STORAGE_TOKEN_RE = re.compile(r"(?<!\d)(\d{2,4})\s*g(?:b)?(?=\D|$)", flags=re.IGNORECASE)
# Match compact multi-capacity forms that share one trailing unit, such as:
# - "128/256GB"
# - "128 / 256 / 512 gb"
# Without this, single-token matching sees only the last value (e.g. 256GB)
# and can miss that the card advertises multiple storage variants.
_COMPACT_MULTI_STORAGE_RE = re.compile(
    r"(?<!\d)(\d{2,4}(?:\s*/\s*\d{2,4})+)\s*g(?:b)?(?=\D|$)",
    flags=re.IGNORECASE,
)

# High-level variant filtering model
# ---------------------------------
# We treat model matching as a "same-family, same-variant" problem:
# 1) Extract a target family key + variant signature from the requested model.
#    Example: "Pixel 9 Pro" -> family "9", signature ("pro",)
#             "Pixel 9"     -> family "9", signature ()
#             "Pixel 6A"    -> family "6", signature ("a",)
# 2) Scan listing text for references to that same family key and extract the
#    variant signature seen at each reference.
# 3) Reject a listing if any same-family reference has a different signature.
#
# Why this works:
# - It catches nearby variants in same model line (e.g. "9 Pro XL" when target
#   is "9 Pro") without requiring a full, brittle model taxonomy.
# - It is brand-agnostic and uses a small curated set of common suffix tokens.
#
# Why it is intentionally heuristic:
# - Seller titles are noisy and often include fragmented text, abbreviations,
#   and specs mixed into model names.
# - We use this as a smoke check (guardrail), not as a canonical model parser.
#
# Important pitfall handled explicitly:
# - Spec tokens like "6GB" or "5G" can look like "family + suffix".
#   We ignore suffixes that are not in _VARIANT_TOKENS so specs are not
#   misclassified as model variants.
#

def normalize_text(text):
    # Shared normalization: lowercase + remove all whitespace.
    return "".join((text or "").lower().split())


def _model_norm(model: Model):
    return " ".join(model.lower().split())


def storage_terms(storage: Storage):
    digits = str(storage)
    return [f"{digits}gb", f"{digits}g"]


def _normalized_terms(values):
    return [normalize_text(value) for value in values]


def text_matches(haystack_text, model_terms, condition_terms, storage_term_values, *, normalized_haystack=None):
    haystack = normalize_text(haystack_text) if normalized_haystack is None else normalized_haystack
    model_ok = any(term in haystack for term in _normalized_terms(model_terms))
    condition_ok = any(term in haystack for term in _normalized_terms(condition_terms))
    storage_ok = any(term in haystack for term in _normalized_terms(storage_term_values))
    return model_ok and condition_ok and storage_ok


def _tokenize_words(text):
    # Keep decimal numbers together (for example "6.7") so screen-size text
    # does not split into stray integer tokens ("6", "7"). Splitting decimals
    # can create false same-family hits (e.g. family key "7") and wrongly
    # reject otherwise valid listings.
    return re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*", (text or "").lower())


def _split_combined_variant_token(token):
    """Split compact variant words like 'promax' or 'proxl' into components."""
    out = []
    remaining = token
    # Keep the token set stable in matching order so split is deterministic.
    ordered = sorted(_VARIANT_TOKENS, key=len, reverse=True)
    while remaining:
        matched = None
        for candidate in ordered:
            if remaining.startswith(candidate):
                matched = candidate
                break
        if matched is None:
            return []
        out.append(matched)
        remaining = remaining[len(matched):]
    return out


def _extract_model_signature(model_text):
    """Return `(family_key, variant_signature)` from model-like text.

    `family_key` is the first token with digits (e.g. `9`, `a54`, `s24`).
    `variant_signature` is a canonical tuple of variant tokens (e.g. `('pro',)`).
    """
    words = _tokenize_words(model_text)
    for idx, token in enumerate(words):
        if not any(ch.isdigit() for ch in token):
            continue
        family_key = token
        variants = []

        # Inline suffix, e.g. "6a" => family "6", variant "a".
        suffix_match = re.match(r"^([a-z]*\d+)([a-z]+)$", token)
        if suffix_match is not None:
            family_key = suffix_match.group(1)
            inline_suffix = suffix_match.group(2)
            if inline_suffix in _VARIANT_TOKENS:
                variants.append(inline_suffix)

        for word in words[idx + 1 : idx + 4]:
            if word in _VARIANT_TOKENS:
                variants.append(word)
                continue
            combined = _split_combined_variant_token(word)
            if combined:
                variants.extend(combined)

        return family_key, tuple(sorted(set(variants)))
    return None, tuple()


def _variant_signatures_for_family(haystack_text, family_key):
    """Extract variant signatures for occurrences matching one family key."""
    words = _tokenize_words(haystack_text)
    signatures = set()
    family_prefix = re.escape(family_key)
    token_re = re.compile(rf"^{family_prefix}([a-z]+)?$")

    for idx, word in enumerate(words):
        match = token_re.match(word)
        if match is None:
            continue

        variants = []
        inline_suffix = match.group(1)
        # Ignore number+unit tokens (e.g. "6gb", "5g") as model-family hits.
        # Without this, titles that mention RAM/network specs can be misread as
        # "other model variants" and valid listings get filtered out.
        if inline_suffix and inline_suffix not in _VARIANT_TOKENS:
            continue
        if inline_suffix and inline_suffix in _VARIANT_TOKENS:
            variants.append(inline_suffix)

        for next_word in words[idx + 1 : idx + 4]:
            # Do not merge variants across another same-family token.
            if token_re.match(next_word):
                break
            if next_word in _VARIANT_TOKENS:
                variants.append(next_word)
                continue
            combined = _split_combined_variant_token(next_word)
            if combined:
                variants.extend(combined)

        signatures.add(tuple(sorted(set(variants))))
    return signatures


def passes_model_smoke_checks(haystack_text, target_model: Model):
    if contains_multi_variant_model_list(haystack_text, target_model):
        return False
    if contains_other_model(haystack_text, target_model):
        return False
    return True


def contains_other_model(haystack_text, target_model: Model):
    """Detect same-family but different-variant references in listing text.

    Example: target "Pixel 9 Pro", listing text contains "9 Pro XL".
    """
    family_key, target_signature = _extract_model_signature(_model_norm(target_model))
    if family_key is None:
        return False

    for sig in _variant_signatures_for_family(haystack_text, family_key):
        if sig != target_signature:
            return True
    return False


def contains_multi_variant_model_list(haystack_text, target_model: Model):
    """Detect list-style multi-variant cards for the same model family."""
    if _SEPARATOR_RE.search(haystack_text or "") is None:
        return False

    family_key, target_signature = _extract_model_signature(_model_norm(target_model))
    if family_key is None:
        return False

    signatures = _variant_signatures_for_family(haystack_text, family_key)
    if len(signatures) < 2:
        return False

    # If any listed variant differs from the target signature, treat as
    # multi-variant and reject.
    return any(sig != target_signature for sig in signatures)


def contains_multi_storage_listing(haystack_text):
    """Return True when listing text advertises multiple storage options.

    Why this exists:
    - Many marketplace cards show one "from" price while listing several
      capacities (for example "128GB | 256GB | 512GB").
    - That card-level price is not guaranteed to be for the requested storage,
      so we treat multi-storage cards as unsafe for capacity-specific scraping.

    Rule:
    - Extract storage-like tokens (`\\d+gb?`, with a 2-4 digit guard).
    - Normalize to distinct numeric capacities.
    - Reject only when more than one *distinct* capacity is present.

    Distinct-value matching matters because many cards repeat the same storage
    in both title and subtitle metadata (for example "128GB ... 128 GB ...").
    Those are single-storage cards and should remain eligible.
    """
    text = haystack_text or ""
    capacities = {match.group(1) for match in _STORAGE_TOKEN_RE.finditer(text)}

    # Expand compact forms like "128/256GB" into {"128", "256"}.
    for match in _COMPACT_MULTI_STORAGE_RE.finditer(text):
        for value in re.findall(r"\d{2,4}", match.group(1)):
            capacities.add(value)

    return len(capacities) > 1
