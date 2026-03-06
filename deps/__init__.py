"""Mutable runtime dependencies used across the app.

Dependencies are intentionally uninitialized at import time. `main.py` must
call `init_deps(...)` before running commands.
"""
import importlib
from contextlib import contextmanager
from pathlib import Path


class _UninitializedDependency:
    def __init__(self, name):
        self._name = name

    def _fail(self):
        raise RuntimeError(f"Dependency '{self._name}' was used before deps.init_deps().")

    def __getattr__(self, _name):
        self._fail()

    def __getitem__(self, _key):
        self._fail()

    def __call__(self, *_args, **_kwargs):
        self._fail()


http_cache = _UninitializedDependency("http_cache")
timing = _UninitializedDependency("timing")
config = _UninitializedDependency("config")
printer = _UninitializedDependency("printer")


def init_deps(
    *,
    profile_performance: bool,
    unicode: bool,
    colors: bool,
    known_prices_data_path: Path,
    http_get_data_dir: Path,
):
    """Initialize global dependency modules for this process run."""
    global http_cache, timing, config, printer

    _http_get_module = importlib.import_module(".http_get", __name__)
    _noop_timing_module = importlib.import_module(".noop_timing", __name__)
    _timing_module = importlib.import_module(".timing", __name__)
    _config_module = importlib.import_module(".config", __name__)
    _printers_module = importlib.import_module(".printers", __name__)

    config = _config_module.Config(
        unicode=unicode,
        colors=colors,
        known_prices_data_path=known_prices_data_path,
        http_get_data_dir=http_get_data_dir,
    )
    http_cache = _http_get_module.HttpCache(
        cache_dir=config.http_get_data_dir / "cache",
        cookie_dir=config.http_get_data_dir / "cookies",
    )
    timing = _timing_module if profile_performance else _noop_timing_module
    printer = _printers_module.ConsolePrinter(unicode=unicode, colors=colors)


@contextmanager
def override(**overrides):
    supported = {"http_cache", "timing", "config", "printer"}
    unknown = set(overrides) - supported
    if unknown:
        raise ValueError(f"Unknown dependency override(s): {', '.join(sorted(unknown))}")

    original = {name: globals()[name] for name in overrides}
    globals().update(overrides)
    try:
        yield
    finally:
        globals().update(original)
