import itertools
import re
import sys
import threading
import time
from contextlib import contextmanager

# Matches ANSI styling sequences (for example, "\x1b[31m" for red text).
# When color output is disabled, we strip these sequences from all rendered text.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Text substitutions used when Unicode output is disabled. This is intentionally
# centralized in the printer layer so all callers can emit rich output while
# transport/output policy (unicode vs ascii) stays in one place.
_UNICODE_MAP = (
    ("⚠️", "!"),
    ("ℹ️", "i"),
    ("✍️", ">"),
    ("✅", "ok"),
    ("⚪", "--"),
    ("💥", "x"),
    ("🧭", ">"),
    ("🏁", "#"),
    ("📡", "@"),
    ("✨", "*"),
    ("▶", ">"),
    ("↑", "^"),
    ("↓", "v"),
    ("→", "->"),
    ("＜", "<"),
    ("╪", "+"),
    ("┼", "+"),
    ("│", "|"),
    ("═", "="),
    ("─", "-"),
    ("█", "@"),
    ("▀", "@"),
    ("▄", "@"),
    ("▟", "@"),
    ("▙", "@"),
    ("▛", "@"),
    ("▜", "@"),
    ("▔", "@"),
    ("▘", "@"),
    ("▗", "@"),
    ("▖", "@"),
    ("▐", "@"),
    ("▌", "@"),
)


class ConsolePrinter:
    """Interactive terminal printer with presentation policy controls.

    This class is the single place where we decide:
    - whether ANSI color codes are preserved or stripped,
    - whether Unicode symbols are preserved or mapped to ASCII,
    - how spinners behave in TTY vs non-TTY contexts.
    """

    def __init__(self, *, unicode=True, colors=True):
        self._unicode = unicode
        self._colors = colors

    def _normalize_text(self, text):
        # Normalize every outbound/inbound terminal string according to
        # configured output policy. This guarantees consistency across both
        # `print(...)` and `input(prompt)`.
        out = str(text)
        if not self._colors:
            out = _ANSI_RE.sub("", out)
        if not self._unicode:
            for source, target in _UNICODE_MAP:
                out = out.replace(source, target)
            out = out.encode("ascii", "ignore").decode("ascii")
        return out

    def print(self, text=""):
        print(self._normalize_text(text))

    def input(self, prompt=""):
        return input(self._normalize_text(prompt))

    @contextmanager
    def spinner(self, text):
        # Spinner text is normalized once, then rendered repeatedly.
        spinner_text = self._normalize_text(text)
        if not sys.stdout.isatty():
            # Non-interactive output (pipes/log files) gets a simple one-shot
            # status line instead of animated carriage-return updates.
            self.print(f"{spinner_text}...")
            yield
            return

        # Braille spinner for unicode terminals, ASCII spinner otherwise.
        frames = ["-", "\\", "|", "/"] if not self._unicode else ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        color = "\033[36m" if self._colors else ""
        reset = "\033[0m" if self._colors else ""
        stop = threading.Event()

        def run():
            for frame in itertools.cycle(frames):
                if stop.is_set():
                    break
                sys.stdout.write(f"\r{color}{frame}{reset} {spinner_text}")
                sys.stdout.flush()
                time.sleep(0.08)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=0.2)
            # Clear the spinner line to avoid leaving animation artifacts in
            # interactive sessions. If colors are off, avoid ANSI clear codes.
            clear_seq = "\r\033[2K" if self._colors else "\r"
            sys.stdout.write(clear_seq)
            sys.stdout.flush()


class NullPrinter:
    """Printer implementation that suppresses output but keeps input alive."""

    def print(self, text=""):
        return None

    def input(self, prompt=""):
        return input(prompt)

    @contextmanager
    def spinner(self, _text):
        # Explicitly no-op so callers can keep a uniform spinner API.
        yield
