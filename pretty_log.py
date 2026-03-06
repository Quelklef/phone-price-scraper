import deps
import glyphs

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
SELLER_W = 10
MODEL_W = 25
_VERIFIED_MARKER = "(v)"
_UNVERIFIED_MARKER = " " * len(_VERIFIED_MARKER)
_KV_LABEL_W = 11


def _emit(text):
    deps.printer.print(text)


def _paint(text, *styles):
    return f"{''.join(styles)}{text}{RESET}"


def _icon(unicode_text):
    return unicode_text


def _result_status(ok):
    if ok:
        return _icon("✅")
    return _icon("⚪")


def _seller_tag(seller):
    label = str(seller).upper()
    return _paint(f"{label:<{SELLER_W}}", BOLD, CYAN)


def _result_prefix(seller, model, condition, storage):
    return (
        f"{_seller_tag(seller)} "
        + _paint(f"{model:<{MODEL_W}}", BOLD, WHITE)
        + " "
        + _paint(storage, BOLD, BLUE)
        + " "
        + _paint(condition, BOLD, YELLOW)
    )


def _verified_column(known_price_match):
    return _paint(_VERIFIED_MARKER, BOLD, GREEN) if known_price_match else _UNVERIFIED_MARKER


def set_model_width_from_models(models):
    global MODEL_W
    if not models:
        return
    MODEL_W = max(MODEL_W, max(len(model) for model in models))


def banner():
    art = [
        "  _____ _ _            _           ____                               ",
        " |  ___(_) | ___ _ __ | |_ _   _  / ___|  ___ _ __ __ _ _ __   ___ _ __ ",
        " | |_  | | |/ _ \\ '_ \\| __| | | | \\___ \\ / __| '__/ _` | '_ \\ / _ \\ '__|",
        " |  _| | | |  __/ | | | |_| |_| |  ___) | (__| | | (_| | |_) |  __/ |   ",
        " |_|   |_|_|\\___|_| |_|\\__|\\__, | |____/ \\___|_|  \\__,_| .__/ \\___|_|   ",
        "                           |___/                       |_|                ",
    ]
    for line in art:
        _emit(_paint(line, CYAN))
    _emit(_paint(glyphs.H_HEAVY * 90, DIM, BLUE))


def section(title):
    _emit(_paint(f"\n{_icon('▶')} {title}", BOLD, BLUE))
    _emit(_paint(glyphs.H * 90, DIM, BLUE))


def fetch(seller, url):
    _emit(
        f"{_paint(_icon('📡'), BOLD, CYAN)} "
        f"{_seller_tag(seller)} {_paint('GET', DIM, WHITE)} {_paint(url, DIM, CYAN)}"
    )


def result(seller, model, condition, storage, price, listing_url=None, known_price_match=False):
    prefix = _result_prefix(seller, model, condition, storage)
    known_segment = _verified_column(known_price_match)
    if price is None:
        _emit(
            f"{_paint(_result_status(False), BOLD, YELLOW)} {prefix} {known_segment} -- "
            + _paint("no listings", ITALIC)
        )
        return

    price_text = f"${price:.2f}"
    line = (
        f"{_paint(_result_status(True), BOLD, GREEN)} {prefix} {known_segment} -- "
        + _paint(price_text, BOLD, GREEN)
        + " "
        + _paint(listing_url or "N/A", DIM, CYAN)
    )
    _emit(line)


def error(seller, model, condition, storage, err):
    prefix = _result_prefix(seller, model, condition, storage)
    _emit(
        f"{_paint(_icon('💥'), BOLD, RED)} {prefix} "
        + _paint(f"error: {err}", BOLD, RED)
    )


def known_price_summary(xref_count, total_rows, by_seller):
    pct = 0.0 if total_rows == 0 else (xref_count / total_rows) * 100.0
    seller_text = ", ".join(f"{count} {seller}" for seller, count in by_seller.items())
    verified_tag = _paint("v", BOLD, GREEN)
    head = _paint("\nPrice is verified (", BOLD, MAGENTA)
    tail = _paint(
        f") for {xref_count} entries (of {total_rows}, {pct:.1f}%). ({seller_text})",
        BOLD,
        MAGENTA,
    )
    _emit(head + verified_tag + tail)


def table_header():
    _emit(_paint(f"\n{_icon('🏁')} Final ranking", BOLD, MAGENTA))


def info(text):
    _emit(f"{_paint(_icon('ℹ️'), BOLD, CYAN)} {text}")


def success(text):
    icon = _paint(_icon("✅"), BOLD, GREEN)
    _emit(f"{icon} {_paint(text, BOLD, GREEN)}")


def warning(text):
    _emit(f"{_paint(_icon('⚠️'), BOLD, YELLOW)} {text}")


def warning_loud(text):
    icon = _paint(_icon("⚠️"), BOLD, YELLOW)
    _emit(f"{icon} {_paint(text, BOLD, YELLOW)}")


def prompt(text):
    return f"{_paint(_icon('✍️'), BOLD, CYAN)} {_paint(text, BOLD, CYAN)} "


def instruction(text):
    icon = _paint(_icon("🧭"), BOLD, CYAN)
    _emit(f"{icon} {_paint(text, BOLD, CYAN)}")


def kv(label, value):
    key = _paint(f"{label + ':':<{_KV_LABEL_W}}", BOLD, BLUE)
    _emit(f"  {key} {value}")


def style_cell(header, value):
    stripped = value.strip()
    if stripped == header:
        return _paint(value, BOLD, BLUE)
    if header == "Seller":
        return _paint(value, BOLD, CYAN)
    if header == "Price" and stripped != "N/A":
        return _paint(value, GREEN)
    if header == "$/Year" and stripped != "N/A":
        return _paint(value, BOLD, MAGENTA)
    if header == "Condition":
        return _paint(value, BOLD, WHITE)
    return value
