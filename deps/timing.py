"""Timing helper for printing a useful performance summary.

At a glance:
- Use `time_stage("name")` (or `stage_start("name")`) to time code blocks.
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


def _next_event_id():
    global _NEXT_EVENT_ID
    event_id = _NEXT_EVENT_ID
    _NEXT_EVENT_ID += 1
    return event_id


def _record(path: tuple[str, ...], elapsed_s: float, event_id: int):
    stat = _STATS.setdefault(path, _StageStat())
    stat.event_ids.add(event_id)
    stat.count += 1
    stat.total_s += elapsed_s
    if elapsed_s > stat.max_s:
        stat.max_s = elapsed_s


def _normalize_stage(stage):
    text = str(stage)
    if not text:
        raise ValueError("stage must be non-empty")
    return text


class StageTimer:
    def __init__(self, path):
        self._path = path
        self._start = time.perf_counter()
        self._ended = False

    def end(self):
        if self._ended:
            return
        self._ended = True
        elapsed = time.perf_counter() - self._start
        event_id = _next_event_id()
        for projection in _iter_path_projections(self._path):
            _record(projection, elapsed, event_id)
        _PATH_STACK.pop()


def stage_start(stage: str):
    norm_stage = _normalize_stage(stage)
    _PATH_STACK.append(norm_stage)
    return StageTimer(tuple(_PATH_STACK))


@contextmanager
def time_stage(stage: str):
    timer = stage_start(stage)
    try:
        yield
    finally:
        timer.end()


def render_summary(*, truncate=True, truncate_threshold=0.05):
    rows = [
        (path, stat.count, stat.total_s, (stat.total_s / stat.count) if stat.count else 0.0, stat.max_s, stat.event_ids)
        for path, stat in _STATS.items()
    ]
    if not rows:
        return ["(no timing data)"]

    rows = _prune_redundant_rows(rows)
    rows.sort(key=lambda row: row[2], reverse=True)
    if truncate:
        top_total = next((row[2] for row in rows if row[0] == ("top",)), rows[0][2])
        threshold_s = top_total * truncate_threshold
        kept_rows = [row for row in rows if row[2] >= threshold_s]
        truncated_count = len(rows) - len(kept_rows)
    else:
        threshold_s = 0.0
        kept_rows = rows
        truncated_count = 0

    stage_w = max(len("Stage Path"), max(len(f" {glyphs.ARROW} ".join(row[0])) for row in kept_rows))
    count_w = max(len("Count"), 5)
    total_w = max(len("Total(s)"), 8)
    avg_w = max(len("Avg(s)"), 7)
    max_w = max(len("Max(s)"), 7)

    def fmt(cells):
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
    for path, count, total_s, avg_s, max_s, _ in kept_rows:
        path_text = f" {glyphs.ARROW} ".join(path)
        lines.append(fmt([
            path_text.ljust(stage_w),
            str(count).rjust(count_w),
            f"{total_s:8.3f}".rjust(total_w),
            f"{avg_s:7.3f}".rjust(avg_w),
            f"{max_s:7.3f}".rjust(max_w),
        ]))
    if truncated_count:
        lines.append(f"{truncated_count} rows {glyphs.LESS_THAN}{threshold_s:.3f}s removed")
    return lines


def _iter_path_projections(path: tuple[str, ...]):
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


def _prune_redundant_rows(rows):
    # Rows with identical event IDs describe the same underlying timed events.
    # Within each event-ID set:
    # 1) Repeatedly: if A is a prefix of B, drop B.
    # 2) After (1) reaches a fixed point, repeatedly: if A is a strict
    #    supersequence of B, drop B.
    grouped: dict[tuple[int, ...], list[tuple]] = {}
    for row in rows:
        grouped.setdefault(tuple(sorted(row[5])), []).append(row)

    def _is_subsequence(subseq, seq):
        if len(subseq) > len(seq):
            return False
        it = iter(seq)
        return all(any(part == cur for cur in it) for part in subseq)

    kept = []
    for group_rows in grouped.values():
        rows_by_path = {row[0]: row for row in group_rows}
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
