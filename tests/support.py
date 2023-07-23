"""Common test support code."""

import asyncio
import contextlib
import textwrap
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List

import log

from clippets import core

try:
    NativeEventLoop = asyncio.ProactorEventLoop
except AttributeError:
    NativeEventLoop = asyncio.SelectorEventLoop

data_dir = Path('/tmp/girok')
msg_filter = set([
    'Blur',
    'Callback',
    'Compose',
    'DescendantBlur',
    'DescendantFocus',
    'Focus',
    'Hide',
    'InvokeLater',
    'Key',
    'Layout',
    'Mount',
    'Resize',
    'Ready',
    'ScreenResume',
    'ScreenSuspend',
    'Show',
    'TableOfContentsUpdated',
    'Unmount',
    'Update',

    'Load',
])


class Namespace:                       # pylint: disable=too-few-public-methods
    """Simple emulation of the argparse.Namespace for the Clippets app."""

    def __init__(self, **kwargs):
        self.raw = False
        self.logf = None
        self.__dict__.update(kwargs)


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


class TempTestFile:
    """A temporary file for testing.

    The only difference is that the string representation is the file's current
    contents.
    """

    def __init__(self, *args, **kwargs):
        self._f = NamedTemporaryFile(*args, **kwargs)

    @property
    def name(self):
        """The name of the temporary file."""
        return self._f.name

    def write(self, *args, **kwargs):
        """Write to the file."""
        return self._f.write(*args, **kwargs)

    def read(self, *args, **kwargs):
        """Reaf from the file."""
        return self._f.read(*args, **kwargs)

    def flush(self):
        """Flush the file."""
        return self._f.flush()

    def close(self):
        """Close the file."""
        return self._f.close()

    def seek(self, *args, **kwargs):
        """Seek within the file."""
        return self._f.seek(*args, **kwargs)

    def __str__(self):
        self._f.seek(0)
        return self._f.read()


async def wait_for_idle():
    loop = asyncio.get_running_loop()
    for _ in range(100):
        if loop.is_idle():
            break
        await asyncio.sleep(0)


class AppRunner:
    """Runs the Clippets application in a controlled manner.

    The app is run under the pytest asyncio loop.

    This 'steals' some code from Textual.
    """

    logf = None

    def __init__(self, snippet_file: TempTestFile, actions: list):
        if self.__class__.logf is None:
            self.__class__.logf = log.Log('/tmp/test.log')
        self.app = core.Clippets(
            Namespace(snippet_file=snippet_file.name))
        self.msg_q = asyncio.Queue()
        self.actions = actions
        self.pilot = None

    async def run(self, *, size: tuple = (80, 35)) -> str:
        """Run the application."""
        coro =  self.app.run_test(
            headless=True, size=size, message_hook=self.on_msg)
        svg = ''
        try:
            async with coro as self.pilot:
                await self.wait_for_message_name('Ready')
                for action in self.actions:
                    await self.apply_action(action)
                print("Actions complete")
                await wait_for_idle()
                print("Now idle")
                self.app.screen._on_timer_update()
                svg = self.app.export_screenshot()
                await self.pilot.press('ctrl+c')
        except Exception as exc:       # pylint: disable=broad-exception-caught
            print("OOPS", exc, file=self.logf)
        except SystemExit:
            print("OOPS Exit", file=self.logf)
        return svg

    async def apply_action(self, action):
        """Apply an action."""
        await self.pilot.press(action)

    async def handle_error(self, name):
        """Handle an error during the app run."""
        if name.startswith('run_test Snippets('):
            print("ERROR for:", name, file=self.logf)
            await self.app._shutdown()
            return True
        else:
            return False

    def on_msg(self, m):
        """Handle a message generated by the app."""
        name = m.__class__.__name__
        if name not in msg_filter:
            print(f'Msg: {m}', file=self.logf)
        self.msg_q.put_nowait(m)

    async def wait_for_message_name(self, name: str):
        """Wait for a given application message."""
        while True:
            m = await self.msg_q.get()
            if m.__class__.__name__ == name:
                break


class AltEventLoop(NativeEventLoop):
    """This wrapping of the event loop to allow idle detection."""

    def is_idle(self):
        end_time = self.time() + self._clock_resolution
        if self._ready:
            return False
        elif self._scheduled:
            idle = self._scheduled[0]._when > end_time
            return idle
        else:
            return True


class AltEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy to use `AltEventLoop`."""

    _loop_factory = AltEventLoop


# Make our enhanced event loop available.
asyncio.set_event_loop_policy(AltEventLoopPolicy())
