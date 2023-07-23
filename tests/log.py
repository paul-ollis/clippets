"""The obligatory simple logger.

This is here to support debugging. It is deliberately simple. It tends to be
more useful when running the test suite. For other debugging, simply using
print and the textual console tool is my typical approach.
"""

import os
import sys
import time
from pathlib import Path


def timestamp():
    """Provide textual timestamps to 3 decimal places."""
    start = time.time()
    now = time.time()
    while True:
        yield f'{now - start:6.3f}'
        now = time.time()


ts = timestamp()
next(ts)


class Log:
    """A very simple debug logger.

    This can be used as a context manager to temporarily redirect stdout to the
    log file.
    """

    def __init__(self, path: Path | str):
        worker = os.environ.get('PYTEST_XDIST_WORKER')
        if worker is None:
            self._path = Path(path)
        else:
            self._path = Path(f'{str(path)}-{worker}')
        self._f = self._path.open(mode='wt', encoding='utf8', buffering=1)
        self._saved_stdout = []
        self._partial_line = ''

    def write(self, text: str):
        """Emulate file.write."""
        lines = text.splitlines(keepends=True)
        if not lines:
            return

        if not lines[0].endswith('\n'):
            self._partial_line += lines[0]
            return

        tm = next(ts)
        self._f.write(f'{tm}: {self._partial_line}{lines[0]}')
        self._partial_line = ''
        lines.pop(0)
        if lines and not lines[-1].endswith('\n'):
            self._partial_line = lines.pop()
        for line in lines:
            self._f.write(f'{tm}: {line}')

    def flush(self):
        """Emulate file.flush.

        This actually flushes any partial line as if it were a complete line.
        This behaviour may change to a simple NOP - still thinking about this.
        """
        if self._partial_line:
            tm = next(ts)
            self._f.write(f'{tm}: {self._partial_line}\n')
            self._partial_line = ''
        self._f.flush()

    def __enter__(self):
        sys.stdout.flush()
        self._saved_stdout.append(sys.stdout)
        sys.stdout = self

    def __exit__(self, *args, **kwargs):
        self.flush()
        sys.stdout = self._saved_stdout.pop()
