from contextlib import contextmanager


class _NoOpTimer:
    def end(self) -> None:
        return None


def stage_start(*_stages: str) -> _NoOpTimer:
    return _NoOpTimer()


@contextmanager
def time_stage(*_stages: str):
    yield


def render_summary(*, truncate: bool = True, truncate_threshold: float = 0.05) -> list[str]:
    return []
