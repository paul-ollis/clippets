"""Code that handles platform specific behaviour."""

import platform
import tempfile
from pathlib import Path

__all__ = [                                                        # noqa: F822
    'get_editor_command',
    'get_winpos',
    'put_to_clipboard',
    'terminal_title',
]

if platform.system() == 'Windows':
    from . import win as _platform
elif platform.system() == 'Linux':
    from . import linux as _platform

for name in __all__:
    d = globals()
    d[name] = getattr(_platform, name)
del _platform

__all__.extend(['SharedTempFile'])


class SharedTempFile(Path):
    """A temporary file that can be shared betweed processes.

    Under Linux we can use NamedTemporaryFile alone to handle all th
    copmplexities. Under Windows, file locking requires that we manage things a
    bit differently.

    This is a subclass of pathlib.Path, but it can also be used as a conetxt
    manager, which handles deletion of the file.
    """

    _flavour = type(Path())._flavour                             # noqa: SLF001

    def __new__(cls, *args, **kwargs):
        # Create a named temporary file with auto-delete disabled. This allows
        # it to be kept closed when not reading or writing to the file. Thus
        # allowing the file to be shared when running under Windows.
        tf = tempfile.NamedTemporaryFile(mode='wt+', delete=False)
        tf.close()
        return super().__new__(cls, tf.name, *args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.unlink()
