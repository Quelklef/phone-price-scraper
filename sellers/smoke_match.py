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
        "a",
        "plus",
        "pro",
        "max",
        "ultra",
        "mini",
        "lite",
        "fe",
        "fold",
        "flip",
        "xl",
        "se",
        "t",
        "r",
        "edge",
        "core",
        "neo",
    }
)
_SEPARATOR_RE = re.compile(r"(?:-|/|\||,|&|\band\b)", flags=re.IGNORECASE)


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
    return re.findall(r"[a-z0-9]+", (text or "").lower())


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
