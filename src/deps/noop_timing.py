from contextlib import contextmanager


class _NoOpTimer:
    def end(self):
        return None


def stage_start(*_stages: str):
    return _NoOpTimer()


@contextmanager
def time_stage(*_stages: str):
    yield


def render_summary(*, truncate=True, truncate_threshold=0.05):
    return []
