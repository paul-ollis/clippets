"""Code that handles platform specific behaviour."""
from __future__ import annotations

import sys
import tempfile
from contextlib import suppress
from pathlib import Path

__all__ = [
    'dump_clipboard',
    'get_editor_command',
    'get_winpos',
    'put_to_clipboard',
    'shared_tempfile',
    'terminal_title',
]

if sys.platform == 'win32':                                  # pragma: no cover
    from .win import (
        dump_clipboard, get_editor_command, get_winpos, put_to_clipboard,
        terminal_title)
elif sys.platform == 'linux':
    from .linux import (
        dump_clipboard, get_editor_command, get_winpos, put_to_clipboard,
        terminal_title)


class SharedTempFile(Path):
    """A Path with a clean_up method."""

    def clean_up(self):
        """Clean up when this file is no longer required."""
        with suppress(OSError):
            self.unlink()


def shared_tempfile():
    """Create a temporary file that can be shared between processes.

    Under Linux we can use NamedTemporaryFile alone to handle all the
    copmplexities. Under Windows, file locking requires that we manage things a
    bit differently.
    """
    tf = tempfile.NamedTemporaryFile(mode='wt+', delete=False)
    tf.close()
    return SharedTempFile(tf.name)
