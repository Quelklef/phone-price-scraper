import argparse
from pathlib import Path

import deps
from core import Model, Storage, normalize_model_name

SUPPORTED_SELLER_KEYS = ("swappa", "ebay", "amazon", "backmarket")
DEFAULT_SEARCH_STORAGES: list[Storage] = [128, 256, 512]
DEFAULT_SEARCH_MODELS: list[Model] = [
    normalize_model_name("Pixel 6a"),
    normalize_model_name("Pixel 6"),
    normalize_model_name("Pixel 6 Pro"),
    normalize_model_name("Pixel 7a"),
    normalize_model_name("Pixel 7"),
    normalize_model_name("Pixel 7 Pro"),
    normalize_model_name("Pixel Tablet"),
    normalize_model_name("Pixel Fold"),
    normalize_model_name("Pixel 8a"),
    normalize_model_name("Pixel 8"),
    normalize_model_name("Pixel 8 Pro"),
    normalize_model_name("Pixel 9a"),
    normalize_model_name("Pixel 9"),
    normalize_model_name("Pixel 9 Pro"),
    normalize_model_name("Pixel 9 Pro XL"),
    normalize_model_name("Pixel 9 Pro Fold"),
    normalize_model_name("Pixel 10"),
    normalize_model_name("Pixel 10 Pro"),
    normalize_model_name("Pixel 10 Pro XL"),
    normalize_model_name("Pixel 10 Pro Fold"),
]

ANALYZE_LONG_HELP = """
Run all sellers and print a ranked comparison table.

Use this when you want the current snapshot of scraped prices.
""".strip()

CONDITION_FILTER_NOTE = (
    "Note: --search-conditions is limited to the known condition set: good,best."
)

_ANSI_RESET = "\033[0m"
_ANSI_BOLD = "\033[1m"
_ANSI_CYAN = "\033[36m"
_ANSI_YELLOW = "\033[33m"
_ANSI_GREEN = "\033[32m"


def _parse_csv(raw_value, field_name):
    raw_items = [item.strip() for item in raw_value.split(",")]
    if any(not item for item in raw_items):
        raise argparse.ArgumentTypeError(
            f"Invalid {field_name} list: empty item found. Use comma-separated values."
        )
    return raw_items


def _parse_choice_csv(raw_value, *, field_name, allowed_values):
    selected = []
    invalid = []
    allowed = tuple(allowed_values)
    allowed_set = set(allowed)
    for item in _parse_csv(raw_value, field_name):
        token = item.strip().lower()
        if token not in allowed_set:
            invalid.append(item)
            continue
        if token not in selected:
            selected.append(token)
    if invalid:
        allowed_text = ",".join(allowed)
        raise argparse.ArgumentTypeError(
            f"Unknown {field_name} values: {', '.join(invalid)}. Valid {field_name}s: {allowed_text}"
        )
    return selected


def _parse_models_csv(raw_value):
    selected: list[Model] = []
    for model in _parse_csv(raw_value, "model"):
        normalized = normalize_model_name(model)
        if normalized not in selected:
            selected.append(normalized)
    return selected


def _parse_storages_csv(raw_value):
    selected: list[Storage] = []
    invalid = []
    for item in _parse_csv(raw_value, "storage"):
        token = item.strip().lower()
        if token.endswith("gb"):
            token = token[:-2].strip()
        if not token.isdigit():
            invalid.append(item)
            continue
        storage_gb = int(token)
        if storage_gb not in selected:
            selected.append(storage_gb)
    if invalid:
        raise argparse.ArgumentTypeError(
            f"Unknown storage values: {', '.join(invalid)}. Example: 128gb,256gb"
        )
    return selected


def _parse_sellers_csv(raw_value):
    return _parse_choice_csv(
        raw_value,
        field_name="seller",
        allowed_values=SUPPORTED_SELLER_KEYS,
    )


def _parse_conditions_csv(raw_value):
    return _parse_choice_csv(
        raw_value,
        field_name="condition",
        allowed_values=("good", "best"),
    )


def _parse_percentage_string(raw_value):
    text = str(raw_value).strip()
    if not text.endswith("%"):
        raise argparse.ArgumentTypeError(
            f"Invalid percentage: {raw_value!r}. Use format like 5%."
        )
    number_text = text[:-1].strip()
    try:
        number = float(number_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid percentage: {raw_value!r}. Use numeric format like 5%."
        ) from exc
    if number < 0 or number > 100:
        raise argparse.ArgumentTypeError(
            f"Invalid percentage: {raw_value!r}. Must be between 0% and 100%."
        )
    return number / 100.0


def _parse_bool(raw_value):
    if isinstance(raw_value, bool):
        return raw_value
    text = str(raw_value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(
        f"Invalid boolean value: {raw_value!r}. Use true/false."
    )


class _UnicodeAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            setattr(namespace, self.dest, option_string != "-U")
            return
        setattr(namespace, self.dest, _parse_bool(values))


class _ColorsAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            setattr(namespace, self.dest, option_string != "-C")
            return
        setattr(namespace, self.dest, _parse_bool(values))


class _DataDirAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        setattr(namespace, "data_dir_explicit", True)


def _style(text, code, *, enabled):
    if not enabled:
        return text
    return f"{code}{text}{_ANSI_RESET}"


def _resolve_data_dir(path):
    return Path(path).expanduser()


def _choose_data_dir(args):
    # If the default data dir is missing, interactively confirm or override it.
    chosen = _resolve_data_dir(args.data_dir)
    if args.data_dir_explicit or chosen.exists():
        return chosen

    custom_path_used = False

    def _prompt_custom_path_tip():
        if not custom_path_used:
            return
        tip_prefix = _style(
            "Tip: next time, pass this explicitly with -d ",
            _ANSI_CYAN,
            enabled=args.colors,
        )
        tip_path = _style(
            str(chosen),
            _ANSI_BOLD + _ANSI_YELLOW,
            enabled=args.colors,
        )
        tip_suffix = _style(
            ". Press Enter to continue. ",
            _ANSI_CYAN,
            enabled=args.colors,
        )
        input(f"{tip_prefix}{tip_path}{tip_suffix}")

    try:
        while not chosen.exists():
            resolved = chosen.resolve()
            prose = _style(
                "Creating data dir at ",
                _ANSI_CYAN,
                enabled=args.colors,
            )
            path = _style(str(resolved), _ANSI_BOLD + _ANSI_YELLOW, enabled=args.colors)
            options = "(yes=Enter, no=Ctrl-C/D, or specify a custom path)"
            user_input = input(
                f"{prose}{path}{_style('. Ok? ', _ANSI_CYAN, enabled=args.colors)}"
                f"{options}{_style(': ', _ANSI_CYAN, enabled=args.colors)}"
            ).strip()
            if not user_input:
                chosen.mkdir(parents=True, exist_ok=True)
                _prompt_custom_path_tip()
                return chosen
            chosen = _resolve_data_dir(Path(user_input))
            custom_path_used = True
        _prompt_custom_path_tip()
        return chosen
    except (KeyboardInterrupt, EOFError):
        print()
        print("Cancelled.")
        raise SystemExit(130)


def build_parser():
    parser = argparse.ArgumentParser(
        add_help=False,
        description="Check phone listing prices from multiple sellers.",
        epilog=None,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    help_group = parser.add_argument_group("help")
    help_group.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit.",
    )
    general_group = parser.add_argument_group("general options")
    general_group.add_argument(
        "-d",
        "--data-dir",
        default="./data",
        metavar="PATH",
        action=_DataDirAction,
        help=(
            "Directory for runtime data files (default: ./data), including "
            "HTTP cache and other persisted scraper data."
        ),
    )
    search_group = parser.add_argument_group("search scope", CONDITION_FILTER_NOTE)
    search_group.add_argument(
        "--search-sellers",
        default=None,
        metavar="LIST",
        help=(
            "Comma-separated sellers to search (e.g. \"swappa,ebay\").\n"
            "Supported sellers: swappa,ebay,amazon,backmarket."
        ),
    )
    search_group.add_argument(
        "--search-models",
        default=None,
        metavar="LIST",
        help=(
            "Comma-separated model list to search (any text labels; "
            "e.g. \"Pixel 6a,Pixel 8 Pro,Some Future Phone\")."
        ),
    )
    search_group.add_argument(
        "--search-storages",
        default=None,
        metavar="LIST",
        help=(
            "Comma-separated storage list to search (e.g. \"128gb,256gb\"). "
            "Default: 128gb,256gb,512gb."
        ),
    )
    search_group.add_argument(
        "--search-conditions",
        default=None,
        metavar="LIST",
        help=(
            "Comma-separated condition list.\n"
            "Supported conditions: good,best. Default: good,best."
        ),
    )
    output_group = parser.add_argument_group("file output")
    output_group.add_argument(
        "-o",
        "--output-csv",
        nargs="?",
        const="results.csv",
        default=None,
        metavar="PATH",
        help="Also write the final table to CSV at PATH (default: results.csv).",
    )
    display_group = parser.add_argument_group("terminal output")
    display_group.add_argument(
        "-u",
        "-U",
        "--unicode",
        dest="unicode",
        nargs="?",
        action=_UnicodeAction,
        default=True,
        metavar="BOOL",
        help=(
            "Unicode output toggle. Accepts true/false "
            "(default: true). -u sets true, -U sets false."
        ),
    )
    display_group.add_argument(
        "-c",
        "-C",
        "--colors",
        dest="colors",
        nargs="?",
        action=_ColorsAction,
        default=True,
        metavar="BOOL",
        help=(
            "Color output toggle. Accepts true/false "
            "(default: true). -c sets true, -C sets false."
        ),
    )
    other_group = parser.add_argument_group("other options")
    other_group.add_argument(
        "-p",
        "--profile-performance",
        action="store_true",
        help="Show timing/profiling details at the end.",
    )
    other_group.add_argument(
        "--profile-truncate-threshold",
        default=_parse_percentage_string("5%"),
        type=_parse_percentage_string,
        metavar="PCT",
        help="Truncate timing rows below this percent of total runtime (e.g. 5%%).",
    )
    other_group.add_argument(
        "--profile-truncate",
        dest="profile_truncate",
        nargs="?",
        const=True,
        type=_parse_bool,
        metavar="BOOL",
        default=True,
        help="Truncate timing table rows. Accepts true/false (default: true).",
    )
    display_group.add_argument(
        "--table-direction",
        choices=("top-to-bottom", "bottom-to-top"),
        default="bottom-to-top",
        help=(
            "Table print direction for terminal readability. "
            "'bottom-to-top' (default) prints rows in reverse and places the header at the end "
            "so recent/lowest rows stay nearest your prompt."
        ),
    )
    parser.description = ANALYZE_LONG_HELP

    return parser


def parse_args():
    parser = build_parser()
    parser.set_defaults(data_dir_explicit=False)
    args = parser.parse_args()
    args.search_models = (
        _parse_models_csv(args.search_models)
        if args.search_models is not None
        else list(DEFAULT_SEARCH_MODELS)
    )
    args.search_storages = (
        _parse_storages_csv(args.search_storages)
        if args.search_storages is not None
        else list(DEFAULT_SEARCH_STORAGES)
    )
    args.search_sellers = (
        _parse_sellers_csv(args.search_sellers)
        if args.search_sellers is not None
        else None
    )
    args.search_conditions = (
        _parse_conditions_csv(args.search_conditions)
        if args.search_conditions is not None
        else ["good", "best"]
    )
    return parser, args


def main():
    _parser, args = parse_args()
    data_dir = _choose_data_dir(args)
    print(f"Using data directory {data_dir.resolve()}\n")
    deps.init_deps(
        profile_performance=args.profile_performance,
        unicode=args.unicode,
        colors=args.colors,
        known_prices_data_path=data_dir / "known-prices.json",
        http_get_data_dir=data_dir / "http_get",
    )
    from analyze import run

    return run(
        profile_performance=args.profile_performance,
        profile_truncate=args.profile_truncate,
        profile_truncate_threshold=args.profile_truncate_threshold,
        output_csv_path=args.output_csv,
        table_direction=args.table_direction,
        search_sellers=args.search_sellers,
        search_models=args.search_models,
        search_storages=args.search_storages,
        search_conditions=args.search_conditions,
    )


if __name__ == "__main__":
    main()
