"""Code that handles platform specific behaviour."""

import sys
import tempfile
from pathlib import Path

__all__ = [
    'dump_clipboard',
    'get_editor_command',
    'get_winpos',
    'put_to_clipboard',
    'SharedTempFile',
    'terminal_title',
]

if sys.platform == 'win32':                                  # pragma: no cover
    from .win import (
        get_editor_command, get_winpos, put_to_clipboard, terminal_title,
        dump_clipboard)
elif sys.platform == 'linux':
    from .linux import (
        get_editor_command, get_winpos, put_to_clipboard, terminal_title,
        dump_clipboard)


class SharedTempFile(Path):
    """A temporary file that can be shared between processes.

    Under Linux we can use NamedTemporaryFile alone to handle all the
    copmplexities. Under Windows, file locking requires that we manage things a
    bit differently.
    """

    # pylint: disable=no-member
    _flavour = getattr(type(Path()), '_flavour', '')

    def __new__(cls, *args, **kwargs) -> 'SharedTempFile':
        """Extend behaviour of Path.__new__.

        Create a named temporary file with auto-delete disabled. This allows it
        to be kept closed when not reading or writing to the file. Thus
        allowing the file to be shared when running under Windows.
        """
        tf = tempfile.NamedTemporaryFile(mode='wt+', delete=False)
        tf.close()
        return super().__new__(cls, tf.name, *args, **kwargs)
