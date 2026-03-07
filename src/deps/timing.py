"""Timing helper for printing a useful performance summary.

At a glance:
- Use `time_stage("name")` (or `stage_start("name")`) to time code blocks.
- Use `time_stage("a", "b", ...)` as shorthand for immediate nested scopes.
- The summary prints count/total/avg/max per stage path.

How paths work:
- If `html.parse` runs inside `top -> seller.amazon`, we record:
  - `top -> seller.amazon -> html.parse` (very specific), and also
  - broader views like `top -> html.parse` and `html.parse`.
- This lets one run answer both:
  - "How expensive is html parsing inside amazon?"
  - "How expensive is html parsing overall?"

Why pruning exists:
- Recording broad + specific views creates duplicate-looking rows.
- Some rows represent the exact same timed events, just with extra path text.
- We remove those duplicates so the output is shorter and easier to scan.

In plain terms:
- Keep one representative row when two rows are timing the same work.
- Usually we keep the shorter path label because it is easier to read.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from itertools import combinations
import time
from typing import NamedTuple, TypedDict

import glyphs


@dataclass
class _StageStat:
    count: int = 0
    total_s: float = 0.0
    max_s: float = 0.0
    event_ids: set[int] = field(default_factory=set)


_STATS: dict[tuple[str, ...], _StageStat] = {}
_PATH_STACK: list[str] = []
_NEXT_EVENT_ID = 1
_PATH_PROJECTIONS_CACHE: dict[tuple[str, ...], tuple[tuple[str, ...], ...]] = {}


class TimingRow(NamedTuple):
    path: tuple[str, ...]
    count: int
    total_s: float
    avg_s: float
    max_s: float
    event_ids: frozenset[int]


Row = TimingRow


class SummaryStats(TypedDict):
    truncated_count: int
    threshold_s: float
    top_total_s: float


def _next_event_id() -> int:
    global _NEXT_EVENT_ID
    event_id = _NEXT_EVENT_ID
    _NEXT_EVENT_ID += 1
    return event_id


def _record(path: tuple[str, ...], elapsed_s: float, event_id: int) -> None:
    stat = _STATS.setdefault(path, _StageStat())
    stat.event_ids.add(event_id)
    stat.count += 1
    stat.total_s += elapsed_s
    if elapsed_s > stat.max_s:
        stat.max_s = elapsed_s


def _normalize_stage(stage: object) -> str:
    text = str(stage)
    if not text:
        raise ValueError("stage must be non-empty")
    return text


class StageTimer:
    def __init__(self, paths: tuple[tuple[str, ...], ...], *, pop_count: int):
        self._paths = paths
        self._pop_count = pop_count
        self._start = time.perf_counter()
        self._ended = False

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        elapsed = time.perf_counter() - self._start
        event_id = _next_event_id()
        all_projections: set[tuple[str, ...]] = set()
        for path in self._paths:
            all_projections.update(_iter_path_projections(path))
        for projection in all_projections:
            _record(projection, elapsed, event_id)
        del _PATH_STACK[-self._pop_count:]


def stage_start(*stages: str) -> StageTimer:
    if not stages:
        raise ValueError("stage_start requires at least one stage")
    norm_stages = tuple(_normalize_stage(stage) for stage in stages)
    prefix_paths: list[tuple[str, ...]] = []
    for stage in norm_stages:
        _PATH_STACK.append(stage)
        prefix_paths.append(tuple(_PATH_STACK))
    return StageTimer(tuple(prefix_paths), pop_count=len(norm_stages))


@contextmanager
def time_stage(*stages: str):
    timer = stage_start(*stages)
    try:
        yield
    finally:
        timer.end()


def render_summary(*, truncate: bool = True, truncate_threshold: float = 0.05) -> list[str]:
    lines, _summary = render_summary_with_stats(
        truncate=truncate,
        truncate_threshold=truncate_threshold,
    )
    return lines


def render_summary_with_stats(
    *,
    truncate: bool = True,
    truncate_threshold: float = 0.05,
) -> tuple[list[str], SummaryStats]:
    rows: list[Row] = [
        Row(
            path=path,
            count=stat.count,
            total_s=stat.total_s,
            avg_s=(stat.total_s / stat.count) if stat.count else 0.0,
            max_s=stat.max_s,
            event_ids=frozenset(stat.event_ids),
        )
        for path, stat in _STATS.items()
    ]
    if not rows:
        return ["(no timing data)"], {
            "truncated_count": 0,
            "threshold_s": 0.0,
            "top_total_s": 0.0,
        }

    rows = _prune_redundant_rows(rows)
    rows.sort(key=lambda row: row.total_s, reverse=True)
    top_total = next((row.total_s for row in rows if row.path == ("top",)), rows[0].total_s)
    if truncate:
        threshold_s = top_total * truncate_threshold
        kept_rows = [row for row in rows if row.total_s >= threshold_s]
        truncated_count = len(rows) - len(kept_rows)
    else:
        threshold_s = 0.0
        kept_rows = rows
        truncated_count = 0

    stage_w = max(len("Stage Path"), max(len(f" {glyphs.ARROW} ".join(row.path)) for row in kept_rows))
    count_w = max(len("Count"), 5)
    total_w = max(len("Total(s)"), 8)
    avg_w = max(len("Avg(s)"), 7)
    max_w = max(len("Max(s)"), 7)

    def fmt(cells: list[str]) -> str:
        return f" {glyphs.V} ".join(cells)

    header = fmt([
        "Stage Path".ljust(stage_w),
        "Count".ljust(count_w),
        "Total(s)".ljust(total_w),
        "Avg(s)".ljust(avg_w),
        "Max(s)".ljust(max_w),
    ])
    sep = f"{glyphs.H}{glyphs.X}{glyphs.H}".join([
        glyphs.H * stage_w,
        glyphs.H * count_w,
        glyphs.H * total_w,
        glyphs.H * avg_w,
        glyphs.H * max_w,
    ])

    lines = [header, sep]
    for row in kept_rows:
        path_text = f" {glyphs.ARROW} ".join(row.path)
        lines.append(fmt([
            path_text.ljust(stage_w),
            str(row.count).rjust(count_w),
            f"{row.total_s:8.3f}".rjust(total_w),
            f"{row.avg_s:7.3f}".rjust(avg_w),
            f"{row.max_s:7.3f}".rjust(max_w),
        ]))
    summary: SummaryStats = {
        "truncated_count": truncated_count,
        "threshold_s": threshold_s,
        "top_total_s": top_total,
    }
    return lines, summary


def _iter_path_projections(path: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    cache_key = path
    cached = _PATH_PROJECTIONS_CACHE.get(cache_key)
    if cached is None:
        n = len(path)
        projections = []
        # For one stage execution, generate path views from most specific to
        # broader views. Example:
        # path=("top", "seller.amazon", "html.parse")
        # produces:
        # - ("top", "seller.amazon", "html.parse")
        # - ("top", "html.parse")
        # - ("seller.amazon", "html.parse")
        # - ("html.parse",)
        #
        # This is what enables both detailed and rolled-up summary rows.
        #
        # IMPORTANT: projected views must preserve the final path item (the
        # event leaf). If projections were allowed to drop that final item, one
        # event like ("a","b","c") would also emit ("a","b"), which belongs to
        # a different event scope and would create cross-scope double-counting
        # artifacts in summary rows.
        leaf = path[-1]
        for k in range(n):
            for idxs in combinations(range(n - 1), k):
                prefix = tuple(path[i] for i in idxs)
                if prefix and prefix[-1] == leaf:
                    continue
                projections.append(prefix + (leaf,))
        cached = tuple(projections)
        _PATH_PROJECTIONS_CACHE[cache_key] = cached
    return cached


def _prune_redundant_rows(rows: list[Row]) -> list[Row]:
    # Rows with identical event IDs describe the same underlying timed events.
    # Within each event-ID set:
    # 1) Repeatedly: if A is a prefix of B, drop B.
    # 2) After (1) reaches a fixed point, repeatedly: if A is a strict
    #    supersequence of B, drop B.
    grouped: dict[frozenset[int], list[Row]] = {}
    for row in rows:
        grouped.setdefault(row.event_ids, []).append(row)

    def _is_subsequence(subseq: tuple[str, ...], seq: tuple[str, ...]) -> bool:
        if len(subseq) > len(seq):
            return False
        it = iter(seq)
        return all(any(part == cur for cur in it) for part in subseq)

    kept: list[Row] = []
    for group_rows in grouped.values():
        rows_by_path: dict[tuple[str, ...], Row] = {row.path: row for row in group_rows}
        active_paths = set(rows_by_path)

        # Phase 1: strict prefix elimination to fixed point.
        changed = True
        while changed:
            changed = False
            to_drop = set()
            active_list = list(active_paths)
            for a in active_list:
                for b in active_list:
                    if a == b:
                        continue
                    if len(a) < len(b) and b[:len(a)] == a:
                        to_drop.add(b)
            if to_drop:
                active_paths -= to_drop
                changed = True

        # Phase 2: strict supersequence elimination to fixed point.
        changed = True
        while changed:
            changed = False
            to_drop = set()
            active_list = list(active_paths)
            for a in active_list:
                for b in active_list:
                    if a == b:
                        continue
                    if len(a) > len(b) and _is_subsequence(b, a):
                        to_drop.add(b)
            if to_drop:
                active_paths -= to_drop
                changed = True

        for path in active_paths:
            kept.append(rows_by_path[path])
    return kept
