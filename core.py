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
    if not lower:
        return base

    # Widely-used line names that are commonly entered without a brand.
    line_prefixes = (
        ("pixel ", "Google Pixel "),
        ("galaxy ", "Samsung Galaxy "),
        ("iphone ", "Apple Iphone "),
        ("ipad ", "Apple Ipad "),
        ("macbook ", "Apple Macbook "),
        ("xperia ", "Sony Xperia "),
        ("lumia ", "Nokia Lumia "),
        ("redmi ", "Xiaomi Redmi "),
        ("poco ", "Xiaomi Poco "),
        ("moto ", "Motorola Moto "),
        ("razr ", "Motorola Razr "),
    )
    for prefix, replacement in line_prefixes:
        if lower.startswith(prefix):
            return replacement + base[len(prefix):]

    # If the first token is a known brand alias, canonicalize the brand token.
    brand_alias_to_canonical = {
        "apple": "Apple",
        "samsung": "Samsung",
        "google": "Google",
        "xiaomi": "Xiaomi",
        "oneplus": "Oneplus",
        "oppo": "Oppo",
        "vivo": "Vivo",
        "realme": "Realme",
        "motorola": "Motorola",
        "huawei": "Huawei",
        "honor": "Honor",
        "sony": "Sony",
        "nokia": "Nokia",
        "asus": "Asus",
        "lenovo": "Lenovo",
        "zte": "Zte",
        "nubia": "Nubia",
        "nothing": "Nothing",
        "cmf": "Cmf",
        "fairphone": "Fairphone",
        "tecno": "Tecno",
        "infinix": "Infinix",
        "itel": "Itel",
        "meizu": "Meizu",
        "sharp": "Sharp",
        "panasonic": "Panasonic",
        "htc": "Htc",
        "blackberry": "Blackberry",
        "alcatel": "Alcatel",
        "tcl": "Tcl",
        "blu": "Blu",
        "cat": "Cat",
        "doogee": "Doogee",
        "umidigi": "Umidigi",
        "ulefone": "Ulefone",
        "oukitel": "Oukitel",
        "iqoo": "Iqoo",
        "micromax": "Micromax",
        "lava": "Lava",
        "intex": "Intex",
        "gionee": "Gionee",
        "leeco": "Leeco",
        "coolpad": "Coolpad",
        "wiko": "Wiko",
    }
    head, _, tail = base.partition(" ")
    canonical_head = brand_alias_to_canonical.get(head.lower())
    if canonical_head is not None:
        return canonical_head if not tail else f"{canonical_head} {tail}"

    return base


class LogicExtractionError(RuntimeError):
    """Raised when seller selectors find cards but cannot extract required fields."""


class KnownPriceMismatchError(RuntimeError):
    """Raised when a known_prices expectation does not match computed output."""
