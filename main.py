import argparse

import deps
from core import Model, Storage, normalize_model_name

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


def build_parser():
    parser = argparse.ArgumentParser(
        description="Check phone listing prices from multiple sellers.",
        epilog=(
            "Known-price mismatches are treated as failures to keep seller parsers honest over time.\n\n"
            + CONDITION_FILTER_NOTE
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
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
    parser.add_argument(
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
    parser.add_argument(
        "-p",
        "--profile-performance",
        action="store_true",
        help="Show timing/profiling details at the end.",
    )
    output_group = parser.add_argument_group("output")
    output_group.add_argument(
        "-o",
        "--output-csv",
        nargs="?",
        const="results.csv",
        default=None,
        metavar="PATH",
        help="Also write the final table to CSV at PATH (default: results.csv).",
    )
    search_group = parser.add_argument_group("search scope")
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
        help="Comma-separated storage list to search (e.g. \"128gb,256gb\").",
    )
    parser.description = ANALYZE_LONG_HELP

    return parser


def parse_args():
    parser = build_parser()
    args = parser.parse_args()
    args.search_models = (
        _parse_models_csv(args.search_models)
        if args.search_models is not None
        else None
    )
    args.search_storages = (
        _parse_storages_csv(args.search_storages)
        if args.search_storages is not None
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
        search_models=args.search_models,
        search_storages=args.search_storages,
    )


if __name__ == "__main__":
    main()
