"""Canonical CLI flag names shared across modules.

Why this module exists:
- Flag names appear in multiple places: argparse definitions, runtime UX copy,
  and any other code that references command-line switches.
- If those string literals are duplicated at each use-site, they can drift
  during refactors (for example, parser accepts `--foo` while logs still say
  `--bar`), which confuses users and hides regressions.
- This module centralizes just the names (long + short aliases) so callers can
  reference one source of truth while still keeping argparse semantics local.

Why this module is intentionally narrow:
- It only tracks names. Argparse behavior details (type/action/metavar/group)
  remain in the parser use-site where they are easiest to read and change.
- Keeping behavior local avoids a heavyweight "parser DSL" and keeps the CLI
  wiring straightforward.

Recommended fail-fast pattern:
- Modules that depend on specific flags should resolve them during module
  initialization (import time), not lazily at first use.
- This makes missing/renamed flags fail early and loudly, instead of silently
  emitting stale help/hint text at runtime.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FlagNames:
    long: str
    short: tuple[str, ...] = ()


_FLAGS: dict[str, FlagNames] = {
    "help": FlagNames("--help", ("-h",)),
    "hints": FlagNames("--hints"),
    "data_dir": FlagNames("--data-dir", ("-d",)),
    "search_sellers": FlagNames("--search-sellers"),
    "search_models": FlagNames("--search-models"),
    "search_storages": FlagNames("--search-storages"),
    "search_conditions": FlagNames("--search-conditions"),
    "output_csv": FlagNames("--output-csv", ("-o",)),
    "unicode": FlagNames("--unicode", ("-u", "-U")),
    "colors": FlagNames("--colors", ("-c", "-C")),
    "profile_performance": FlagNames("--profile-performance", ("-p",)),
    "prune_http_cache": FlagNames("--prune-http-cache"),
    "profile_truncate_threshold": FlagNames("--profile-truncate-threshold"),
    "profile_truncate": FlagNames("--profile-truncate"),
    "table_direction": FlagNames("--table-direction"),
}


def require_flag(name: str) -> FlagNames:
    flag = _FLAGS.get(name)
    if flag is None:
        known = ", ".join(sorted(_FLAGS))
        raise RuntimeError(f"Unknown CLI flag key: {name!r}. Known keys: {known}")
    return flag
