from contextlib import contextmanager


class _NoOpTimer:
    def end(self):
        return None


def stage_start(_stage: str):
    return _NoOpTimer()


@contextmanager
def time_stage(_stage: str):
    yield


def render_summary():
    return []
