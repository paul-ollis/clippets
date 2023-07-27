"""Common test support code."""

import asyncio
import contextlib
import textwrap
import traceback
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List

import log

from textual.app import App
from textual.events import (
    Click, MouseDown, MouseScrollDown, MouseScrollUp, MouseUp)
from textual.geometry import Offset
from textual.pilot import _get_mouse_message_arguments
from textual.walk import walk_depth_first
from textual.widget import Widget

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


def all_pumps(app: App):
    """Iterate over all (active) message pumps."""
    yield app
    yield from walk_depth_first(app.screen)


async def click(                                                # noqa: PLR0913
    pilot,
    button: str = 'left',
    selector: type[Widget] | str | None = None,
    offset: Offset = Offset(),
    shift: bool = False,
    meta: bool = False,
    control: bool = False,
) -> None:
    """Simulate clicking or scrolling with the mouse.

    Args:
        selector: The widget that should be clicked. If None, then the click
            will occur relative to the screen. Note that this simply causes
            a click to occur at the location of the widget. If the widget is
            currently hidden or obscured by another widget, then the click may
            not land on it.
        offset: The offset to click within the selected widget.
        shift: Click with the shift key held down.
        meta: Click with the meta key held down.
        control: Click with the control key held down.
    """
    # pylint: disable=too-many-arguments
    app = pilot.app
    screen = app.screen
    if selector is not None:
        target_widget = screen.query_one(selector)
    else:
        target_widget = screen

    cls = MouseDown
    bn = 0
    if button in ('left', 'right'):
        bn = 1 if button == 'left' else 3
    elif button == 'up':
        cls = MouseScrollUp
    elif button == 'down':
        cls = MouseScrollDown
    else:
        msg = f'Mouse button name {button!r} is invalid'
        raise RuntimeError(msg)
    message_arguments = _get_mouse_message_arguments(
        target_widget, offset, button=bn, shift=shift, meta=meta,
        control=control
    )
    print("MOUSE", message_arguments)
    await wait_for_idle(pilot)
    if cls is MouseDown:
        app.post_message(MouseDown(**message_arguments))
        app.post_message(MouseUp(**message_arguments))
        app.post_message(Click(**message_arguments))
    else:
        app.post_message(cls(**message_arguments))
    await pilot.pause(0.01)


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


async def wait_for_idle(pilot, app: App | None = None):
    """Wait for the asyncio event loop to become idle."""
    def message_queue_is_empty(p):
        return p._message_queue.empty() and not p._pending_message

    loop = asyncio.get_running_loop()
    for i in range(100):
        pumps_are_idle = True
        screen_is_idle = True
        if app:
            for p in all_pumps(app):
                if not message_queue_is_empty(p):
                    pumps_are_idle = False
                    break
            screen = app.screen
            if screen:
                a = screen._callbacks
                b = screen._next_callbacks
                c = not screen._message_queue.empty()
                d = screen._pending_message
                screen_is_idle = not any((a, b, c, d))
        if loop.is_idle() and pumps_are_idle:
            break
        delay = 0 if i < 30 else 0.01
        await asyncio.sleep(delay)
    else:
        msg = 'Call to wait_for_idle: Never reached IDLE state'
        raise RuntimeError(msg)


class AppRunner:
    """Runs the Clippets application in a controlled manner.

    The app is run under the pytest asyncio loop.

    This 'steals' some code from Textual.

    :actions:
        A list of actions to perform. Each entry is a string that get
        interpreted as described for the following examples:

        pause:0.2
            Pause for a short time.
        left:group-1
            Perform a left mouse button click on the widget with the ID
            'group-1'. The word before the colon identifies the button and
            any modifier keys. Button names are 'left', ;right', 'up' and
            'down. Modifiers are not yet supported.
        f1
            Press the F1 key. Any action without a colon character is
            interpreted as a key tp be pressed.
    """

    logf = None

    def __init__(self, snippet_file: TempTestFile, actions: list):
        if self.__class__.logf is None:
            self.__class__.logf = log.Log('/tmp/test.log')
        self.app = core.Clippets(
            Namespace(snippet_file=snippet_file.name, test_mode=True))
        self.msg_q = asyncio.Queue()
        self.actions = actions
        self.pilot = None

    async def run(
            self, *, size: tuple = (80, 35), post_delay: float= 0.0) -> str:
        """Run the application."""
        coro =  self.app.run_test(
            headless=True, size=size, message_hook=self.on_msg)
        svg = ''
        tb = ''
        try:
            async with coro as self.pilot:
                await self.wait_for_message_name('Ready')
                for action in self.actions:
                    await self.apply_action(action)
                self.app.refresh()
                self.pilot._wait_for_screen()
                self.app.screen._on_timer_update()
                await wait_for_idle(self.pilot, self.app)
                # TODO: I would like to remove this delay.
                if post_delay:
                    await asyncio.sleep(post_delay)
                svg = self.app.export_screenshot()
                await self.pilot.press('ctrl+c')
        except Exception as exc:       # pylint: disable=broad-exception-caught
            tb = traceback.format_exception(exc)
        except SystemExit as exc:
            tb = traceback.format_exception(exc)
        return svg, tb

    async def apply_action(self, action):
        """Apply an action."""
        cmd, _, arg = action.partition(':')
        if arg:
            if cmd == 'pause':
                await asyncio.sleep(float(arg))
            else:
                selector = f'#{arg}'
                widgets = self.app.query(selector)
                if not widgets or len(widgets) > 1:
                    names = []
                    root, *_ = arg.partition('-')
                    for w in self.app.walk():
                        if w.uid().startswith(root):
                            names.append(w.uid())
                    msg = f'Bad widget ID: {arg}, simliar names = {names}'
                    raise RuntimeError(msg)
                await click(self.pilot, button=cmd, selector=selector)
                await wait_for_idle(self.pilot, self.app)
        else:
            await self.pilot.press(action)
            await wait_for_idle(self.pilot, self.app)

    def on_msg(self, m):
        """Handle a message generated by the app."""
        if m.__class__.__name__ not in msg_filter:
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
        """Determine if the event loop is idle.

        The loop is considered idle if all of the following are true.

        - There are no queued 'ready' actions.
        - No scheduled actions are due.
        """
        if self._ready:
            return False
        elif self._scheduled:
            end_time = self.time() + self._clock_resolution
            sched_time = self._scheduled[0]._when - end_time
            # TODO: Can I make the value below 0.0?
            return sched_time >= 0.01                           # noqa: PLR2004
        else:
            return True


class AltEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy to use `AltEventLoop`."""

    _loop_factory = AltEventLoop


# Make our enhanced event loop available.
asyncio.set_event_loop_policy(AltEventLoopPolicy())
