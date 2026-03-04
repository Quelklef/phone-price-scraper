import argparse

import deps

ANALYZE_LONG_HELP = """
Run all sellers and print a ranked comparison table.

Use this when you want the current snapshot of scraped prices.
If any known-good price no longer matches computed output, the run fails so you
can investigate the seller parser drift.
""".strip()


class _ColorsAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        enabled = option_string in {"-c", "--colors"}
        setattr(namespace, self.dest, enabled)


class _UnicodeAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        enabled = option_string in {"-u", "--unicode"}
        setattr(namespace, self.dest, enabled)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Check used Pixel phone prices from multiple sellers.",
        epilog="Known-price mismatches are treated as failures to keep seller parsers honest over time.",
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
    parser.description = ANALYZE_LONG_HELP

    return parser


def parse_args():
    parser = build_parser()
    args = parser.parse_args()
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
    )


if __name__ == "__main__":
    main()
