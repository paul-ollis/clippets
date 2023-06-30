"""Common test support code."""

import contextlib
import textwrap
from pathlib import Path
from typing import List

data_dir = Path('/tmp/girok')


class ApproxInt(int):
    """An integer that can approximately compare as equal.

    By default a range of plus or minus 1 is allowed.
    """

    def __eq__(self, other):
        a, b = getattr(self, 'limits', (-1, 1))
        return self + a <= other <= self + b

    def set_limits(self, a, b) -> 'ApproxInt':
        """Override the default limits."""
        self.limits = a, b
        return self


def clean_text_lines(text: str) -> List[str]:
    """Dedent and remove unwanted blank lines from text."""
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    lines = ['' if line.strip() == '|' else line for line in lines]
    trailing_blanks = []
    while lines and not lines[-1].strip():
        trailing_blanks.append(lines.pop())
    dedented = textwrap.dedent('\n'.join(lines))
    clean_lines = dedented.splitlines()
    while trailing_blanks:
        clean_lines.append(trailing_blanks.pop())
    return clean_lines


def clean_text(text):
    """Dedent and remove unwanted blank lines from text."""
    return '\n'.join(clean_text_lines(text)) + '\n'


def populate(f, text):
    """Populate a snippet file using given text."""
    cleaned_text = clean_text(text)
    f.write(cleaned_text)
    f.flush()
    return cleaned_text


@contextlib.contextmanager
def suspend_capture(cap_fix):
    """Temporarily stop output capture."""
    getattr(cap_fix, '_suspend')()
    yield
    getattr(cap_fix, '_resume')()
