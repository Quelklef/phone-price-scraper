"""Timing helper for printing a useful performance summary.

At a glance:
- Use `time_stage("name")` (or `stage_start("name")`) to time code blocks.
- The summary prints count/total/avg/max per stage path.

How paths work:
- If `html.parse` runs inside `program -> seller.amazon`, we record:
  - `program -> seller.amazon -> html.parse` (very specific), and also
  - broader views like `program -> html.parse` and `html.parse`.
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
_CTX_STACK: list[str] = []
_NEXT_EVENT_ID = 1
_PATH_PROJECTIONS_CACHE: dict[tuple[tuple[str, ...], str], tuple[tuple[str, ...], ...]] = {}


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
    def __init__(self, stage, ctx_before):
        self._stage = stage
        self._ctx_before = ctx_before
        self._start = time.perf_counter()
        self._ended = False

    def end(self):
        if self._ended:
            return
        self._ended = True
        elapsed = time.perf_counter() - self._start
        event_id = _next_event_id()
        for path in _iter_paths_for_stage(self._ctx_before, self._stage):
            _record(path, elapsed, event_id)
        _CTX_STACK.pop()


def stage_start(stage: str):
    norm_stage = _normalize_stage(stage)
    ctx_before = tuple(_CTX_STACK)
    _CTX_STACK.append(norm_stage)
    return StageTimer(norm_stage, ctx_before)


@contextmanager
def time_stage(stage: str):
    timer = stage_start(stage)
    try:
        yield
    finally:
        timer.end()


def render_summary():
    rows = [
        (path, stat.count, stat.total_s, (stat.total_s / stat.count) if stat.count else 0.0, stat.max_s, stat.event_ids)
        for path, stat in _STATS.items()
    ]
    if not rows:
        return ["(no timing data)"]

    rows = _prune_redundant_rows(rows)
    rows.sort(key=lambda row: row[2], reverse=True)
    program_total = next((row[2] for row in rows if row[0] == ("program",)), rows[0][2])
    threshold_s = program_total * 0.05
    kept_rows = [row for row in rows if row[2] >= threshold_s]
    truncated_count = len(rows) - len(kept_rows)

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


def _iter_paths_for_stage(context: tuple[str, ...], stage: str):
    cache_key = (context, stage)
    cached = _PATH_PROJECTIONS_CACHE.get(cache_key)
    if cached is None:
        n = len(context)
        paths = []
        # For one stage execution, generate all path views from most specific
        # to broader views. Example:
        # context=("program", "seller.amazon"), stage="html.parse"
        # produces:
        # - ("program", "seller.amazon", "html.parse")
        # - ("program", "html.parse")
        # - ("seller.amazon", "html.parse")
        # - ("html.parse",)
        #
        # This is what enables both detailed and rolled-up summary rows.
        for k in range(n + 1):
            for idxs in combinations(range(n), k):
                prefix = tuple(context[i] for i in idxs)
                if prefix and prefix[-1] == stage:
                    continue
                paths.append(prefix + (stage,))
        cached = tuple(paths)
        _PATH_PROJECTIONS_CACHE[cache_key] = cached
    return cached


def _is_subsequence(shorter: tuple[str, ...], longer: tuple[str, ...]):
    if len(shorter) > len(longer):
        return False
    it = iter(longer)
    return all(any(part == cur for cur in it) for part in shorter)


def _prune_redundant_rows(rows):
    # If two rows come from the same timed event IDs, they are timing the same
    # underlying work. In that case, keep just one row.
    #
    # Example:
    # - "html.parse"
    # - "program -> seller.amazon -> html.parse"
    # If both rows contain the same event IDs, both rows say the same thing in
    # practice; one is just wordier.
    #
    # We keep the shorter label when possible so the table stays readable.
    # The actual timing values are not lost because both rows came from the
    # same exact events.
    keep = [True] * len(rows)
    for i, row_i in enumerate(rows):
        if not keep[i]:
            continue
        path_i = row_i[0]
        events_i = row_i[5]
        for j, row_j in enumerate(rows):
            if i == j or not keep[j]:
                continue
            path_j = row_j[0]
            events_j = row_j[5]
            if events_i != events_j:
                continue
            if len(path_i) < len(path_j) and _is_subsequence(path_i, path_j):
                keep[j] = False
            elif len(path_j) < len(path_i) and _is_subsequence(path_j, path_i):
                keep[i] = False
                break
            elif len(path_i) == len(path_j) and path_j < path_i:
                keep[i] = False
                break
    return [row for idx, row in enumerate(rows) if keep[idx]]
