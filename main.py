import argparse

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
If any known-good price no longer matches computed output, the run fails so you
can investigate the seller parser drift.
""".strip()

CONDITION_FILTER_NOTE = (
    "No --search-conditions flag is provided on purpose. "
    "Condition handling is seller-specific and not a simple global text filter: "
    "Swappa maps best->(new,mint) and good->(good); "
    "eBay maps to specific condition buckets/facet IDs; "
    "Amazon maps to facet expression IDs (best=new, good=renewed|used); "
    "BackMarket maps to quality labels and then resolves condition-context variant pages."
)


class _ColorsAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        enabled = option_string in {"-c", "--colors"}
        setattr(namespace, self.dest, enabled)


class _UnicodeAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        enabled = option_string in {"-u", "--unicode"}
        setattr(namespace, self.dest, enabled)


def _parse_csv(raw_value, field_name):
    raw_items = [item.strip() for item in raw_value.split(",")]
    if any(not item for item in raw_items):
        raise argparse.ArgumentTypeError(
            f"Invalid {field_name} list: empty item found. Use comma-separated values."
        )
    return raw_items


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
    selected = []
    invalid = []
    for item in _parse_csv(raw_value, "seller"):
        key = item.strip().lower()
        if key not in SUPPORTED_SELLER_KEYS:
            invalid.append(item)
            continue
        if key not in selected:
            selected.append(key)
    if invalid:
        valid = ", ".join(SUPPORTED_SELLER_KEYS)
        raise argparse.ArgumentTypeError(
            f"Unknown seller values: {', '.join(invalid)}. Valid sellers: {valid}"
        )
    return selected


def build_parser():
    parser = argparse.ArgumentParser(
        add_help=False,
        description="Check phone listing prices from multiple sellers.",
        epilog=(
            "Known-price mismatches are treated as failures to keep seller parsers honest over time.\n\n"
            + CONDITION_FILTER_NOTE
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    help_group = parser.add_argument_group("help")
    help_group.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit.",
    )
    search_group = parser.add_argument_group("search scope")
    search_group.add_argument(
        "--search-sellers",
        default=None,
        metavar="LIST",
        help="Comma-separated sellers to search (e.g. \"swappa,ebay\").",
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
        "--no-unicode",
        dest="unicode",
        nargs=0,
        action=_UnicodeAction,
        default=True,
        help="Unicode output toggle (-u/--unicode default, -U/--no-unicode).",
    )
    display_group.add_argument(
        "-c",
        "-C",
        "--colors",
        "--no-colors",
        dest="colors",
        nargs=0,
        action=_ColorsAction,
        default=True,
        help="Color output toggle (-c/--colors default, -C/--no-colors).",
    )
    other_group = parser.add_argument_group("other options")
    other_group.add_argument(
        "-p",
        "--profile-performance",
        action="store_true",
        help="Show timing/profiling details at the end.",
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
    return parser, args


def main():
    _parser, args = parse_args()
    deps.init_deps(
        profile_performance=args.profile_performance,
        unicode=args.unicode,
        colors=args.colors,
    )
    from analyze import run

    return run(
        profile_performance=args.profile_performance,
        output_csv_path=args.output_csv,
        table_direction=args.table_direction,
        search_sellers=args.search_sellers,
        search_models=args.search_models,
        search_storages=args.search_storages,
    )


if __name__ == "__main__":
    main()
