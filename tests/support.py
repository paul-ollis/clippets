"""Common test support code."""
from __future__ import annotations

import os
import textwrap
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

import log

from clippets import robot

# Time to wait to allow Clippets to detect that the editor has exited.
epause = 'pause:0.01'

msg_filter = set([
    'Blur',
    'Callback',
    'Click',
    'Compose',
    'DescendantBlur',
    'DescendantFocus',
    'ExitApp',
    'Focus',
    'Hide',
    'InvokeLater',
    'Key',
    'Layout',
    'Load',
    'Mount',
    'MouseDown',
    'MouseUp',
    'Resize',
    'Ready',
    'ScreenResume',
    'ScreenSuspend',
    'Show',
    'TableOfContentsUpdated',
    'Unmount',
    'Update',
    'UpdateScroll',
])
long_infile_text = '''
    Main
      @text@
        Snippet 1
      @text@
        Snippet 2
      @text@
        Snippet 3
    Second
      @text@
        Snippet 4
      @text@
        Snippet 5
    Third
      @text@
        Snippet 6
      @text@
        Snippet 7
      @text@
        Snippet 8
      @text@
        Snippet 9
    Fourth
      @text@
        Snippet 10
      @text@
        Snippet 11
      @text@
        Snippet 12
      @text@
        Snippet 13
      @text@
        Snippet 14
'''


class EditSessionWasNotStoppedError(Exception):
    """Raised if an editing session failed to stop."""


def clean_text_lines(text: str) -> list[str]:
    """Dedent and remove unwanted blank lines from text.

    A line consisting of a single '|' character is treated as a blank line and
    may be used to add leading or tailing blank lines.
    """
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
    f.write_text(cleaned_text)
    return cleaned_text


@contextmanager
def fix_named_temp_file(name: str):
    """Provide a temporary non-existant, named file."""
    p = Path(name)
    assert not p.exists()
    yield FixNamedTestFile(name)
    if p.exists():
        p.unlink()                                           # pragma: no cover


@dataclass
class FixNamedTestFile:
    """A very simple emulation of a TempTestFile.

    Used when:

    - the name must be the same for every test run.
    - the file must not exist.
    """

    name: str


class TempTestFile:
    """A named temporary file for testing.

    This uses
    The main difference is that the string representation is the file's current
    contents.
    """

    def __init__(self, *args, **kwargs):
        kwargs['delete'] = False
        f = NamedTemporaryFile(*args, **kwargs)
        self._name = f.name
        f.close()

    @property
    def name(self):
        """Get the name of the temporary file."""
        return self._name

    def backup_paths(self) -> list[Path]:
        """Get Path instances for any backup files."""
        paths = []
        for i in range(1, 11):
            bak_path = Path(f'{self._name}.bak{i}')
            if bak_path.exists():
                paths.append(bak_path)
        return sorted(paths)

    def _cleanup(self):
        for bak_path in self.backup_paths():
            with suppress(OSError):
                bak_path.unlink()
        p = Path(self.name)
        if p.exists():
            with suppress(OSError):                          # pragma: no cover
                p.unlink()
        assert not p.exists()

    def close(self):
        """Close the file and delete this file plus any backups."""
        self._cleanup()

    def write_text(self, text):
        """Write given text as the entire file's content."""
        with open(self._name, 'wt', encoding='utf-8') as f:
            f.write(text)

    def delete(self):
        """Delete the file."""
        Path(self.name).unlink()

    def __str__(self):
        with open(self._name, 'rt', encoding='utf-8') as f:
            return f.read()


class EditTempFile(TempTestFile):
    """A version of TempTestFile with special Clippet editing support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._output = None
        self._has_run = False
        self._prev_text = ''

    def _load(self):
        text = str(self)
        lines = text.splitlines()
        self._has_run = lines and lines[0] == '::action occurred::'
        self._prev_text = '\n'.join(lines[1:])

    @property
    def prev_text(self):
        """The text that was replaced by the last edit."""
        self._load()
        return self._prev_text


class AppRunner(robot.AppRunner):
    """Runs the Clippets application in a controlled manner."""

    logf = None

    def __init__(self, *args, control_editor: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        if self.__class__.logf is None:
            self.__class__.logf = log.Log('/tmp/test.log')
        if control_editor:
            self.watch_file = TempTestFile()
            os.environ['CLIPPETS_TEST_WATCH_FILE'] = self.watch_file.name
        else:
            self.watch_file = None
            os.environ['CLIPPETS_TEST_WATCH_FILE'] = ''

    def clean_up(self) -> None:
        """Perform post-run clean up."""
        super().clean_up()
        if self.watch_file is not None:
            self.watch_file.close()
            raise EditSessionWasNotStoppedError

    def on_msg(self, m):
        """Handle a message generated by the app."""
        # An exception here can cause things to hang. Textual will try to
        # display the error and exit, but to do so it sends messages, which
        # call this ...
        try:
            if m.__class__.__name__ not in msg_filter:
                print(f'Msg: {m}', file=self.logf)
        except Exception:              # pylint: disable=broad-exception-caught
            pass
        super().on_msg(m)

    async def exec_end_edit(self, arg):
        """Execute a end_edit action."""
        self.watch_file.close()
        self.watch_file = None
