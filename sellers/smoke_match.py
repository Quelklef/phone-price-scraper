"""Shared smoke checks used by multiple marketplace seller parsers.

Purpose:
- Provide defensive text filters that reject obviously off-target cards even
  when marketplace query params are present.
- Keep normalization behavior consistent across seller parsers so known-price tests
  remain coherent.

These checks are intentionally heuristic. They should bias toward safety
(rejecting suspicious cards) but avoid overfitting to one site's markup.
"""

import re

from core import Model, Storage


def normalize_text(text):
    # Shared normalization: lowercase + remove all whitespace.
    # This lets checks behave consistently across punctuation/spacing variants.
    return "".join((text or "").lower().split())


def _model_norm(model: Model):
    """Canonical lowercased model name with collapsed whitespace."""
    return " ".join(model.value.lower().split())


def _model_tail(model: Model):
    """Model name without leading 'pixel ' prefix (e.g. '8 pro')."""
    return _model_norm(model).removeprefix("pixel ").strip()


def storage_terms(storage: Storage):
    # Accept both "gb" and "g" forms (e.g. "128gb" and "128g").
    digits = "".join(ch for ch in storage if ch.isdigit())
    return [f"{digits}gb", f"{digits}g"]


def _normalized_terms(values):
    """Normalize term list once before membership checks."""
    return [normalize_text(value) for value in values]


def text_matches(haystack_text, model_terms, condition_terms, storage_term_values, *, normalized_haystack=None):
    """Basic three-way term matcher on normalized text.

    A card is considered a text match only if model, condition, and storage all
    have at least one matching term.
    """
    haystack = normalize_text(haystack_text) if normalized_haystack is None else normalized_haystack
    model_ok = any(term in haystack for term in _normalized_terms(model_terms))
    condition_ok = any(term in haystack for term in _normalized_terms(condition_terms))
    storage_ok = any(term in haystack for term in _normalized_terms(storage_term_values))
    return model_ok and condition_ok and storage_ok


def _build_family_variants():
    """Precompute numeric Pixel-family variant tails.

    Example family `8` may include `8`, `8a`, `8pro`, etc. Used by
    multi-variant-list detection.
    """
    variants = {}
    for model in Model:
        tail = normalize_text(_model_tail(model))
        family_match = re.match(r"(\d+)", tail)
        if family_match is None:
            continue
        family = family_match.group(1)
        variants.setdefault(family, set()).add(tail)
    return {family: frozenset(values) for family, values in variants.items()}


_FAMILY_VARIANTS = _build_family_variants()


def passes_model_smoke_checks(haystack_text, target_model: Model):
    """Shared model-level smoke checks used by marketplace seller parsers.

    Current policy:
    - reject list-style multi-variant titles,
    - reject strict-superstring model mismatches.
    """
    if contains_multi_variant_model_list(haystack_text, target_model):
        return False
    if contains_other_model(haystack_text, target_model):
        return False
    return True


def contains_other_model(haystack_text, target_model: Model):
    # Keep this coherent with normalize_text-based matching used by seller parsers.
    haystack = normalize_text(haystack_text)
    target_norm = normalize_text(_model_norm(target_model))
    for model in Model:
        if model == target_model:
            continue
        other_norm = normalize_text(_model_norm(model))
        # Only reject strict superstring models, e.g. for target "Pixel 9 Pro",
        # reject cards containing "Pixel 9 Pro XL" or "Pixel 9 Pro Fold".
        if target_norm not in other_norm or other_norm == target_norm:
            continue
        if other_norm in haystack:
            return True
    return False


def contains_multi_variant_model_list(haystack_text, target_model: Model):
    """Detect "variant list" model titles like "Pixel 8 - 8 Pro".

    Why this exists:
    - Some marketplace cards bundle multiple model variants in one title
      (for example "Pixel 8 / 8 Pro"), where the shown low price frequently
      belongs to a *different* variant than the target model.
    - We choose to drop these cards as a conservative guardrail.

    Important caveat:
    - This is a heuristic and not ideal because it can drop legitimate
      listings, including true low-price phones, when titles use list-style
      punctuation across variants.
    """
    # Keep this coherent with normalize_text-based matching used by seller parsers.
    haystack = normalize_text(haystack_text)
    target_tail = normalize_text(_model_tail(target_model))
    if not target_tail:
        return False

    # This heuristic currently targets numeric Pixel families where list-style
    # variant titles are common (e.g. "8", "8 pro", "8a", "8 pro xl").
    family_match = re.match(r"(\d+)", target_tail)
    if family_match is None:
        return False
    family = family_match.group(1)
    if not family.isdigit():
        return False

    # "a" is attached (e.g. "6a"), and normalized "pro"/"xl"/"fold" are too.
    variant_suffix = r"(?:a|pro(?:xl|fold)?)?"
    variant = rf"{family}{variant_suffix}"
    separator = r"(?:-|/|\||,|&|\band\b)"
    list_pattern = rf"{variant}\s*{separator}\s*{variant}"
    if not re.search(list_pattern, haystack, flags=re.IGNORECASE):
        return False

    # If the card contains a list pattern and includes a same-family variant
    # that differs from target (e.g. target=8 Pro, card mentions "8"), reject.
    family_variants = _FAMILY_VARIANTS.get(family, frozenset())
    if target_tail not in family_variants:
        return True
    for other in family_variants:
        if other == target_tail:
            continue
        if other in haystack:
            return True
    return False
