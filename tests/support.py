"""Common test support code."""
from __future__ import annotations

import asyncio
import os
import textwrap
import time
import traceback
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable

import log

from textual.app import App
from textual.css.query import NoMatches
from textual.events import (
    Click, MouseDown, MouseMove, MouseScrollDown, MouseScrollUp, MouseUp)
from textual.geometry import Offset
from textual.pilot import _get_mouse_message_arguments
from textual.walk import walk_depth_first
from textual.widget import Widget

from clippets import core

try:
    NativeEventLoop = asyncio.ProactorEventLoop
except AttributeError:
    NativeEventLoop = asyncio.SelectorEventLoop

# Time to wait to allow Clippets to detect that the editor has exited.
epause = 'pause:0.01'

data_dir = Path('/tmp/girok')
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

def all_pumps(app: App):
    """Iterate over all (active) message pumps."""
    yield app
    yield from walk_depth_first(app.screen)


async def click(                                                # noqa: PLR0913
    pilot,
    button: str,
    op: str,
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
    target_widget = screen.query_one(selector)

    cls = Click
    bn = 0
    if op == 'drag_release':
        cls = MouseMove
    elif op == 'leftdown':
        cls = MouseDown
    if button in ('left', 'right'):
        bn = 1 if button == 'left' else 3
    elif button == 'down':
        cls = MouseScrollDown
    else:                                                    # pragma: no cover
        msg = f'Mouse button name {button!r} is invalid'
        raise RuntimeError(msg)
    message_arguments = _get_mouse_message_arguments(
        target_widget, offset, button=bn, shift=shift, meta=meta,
        control=control
    )
    await wait_for_idle(pilot)
    if cls is Click:
        app.post_message(MouseDown(**message_arguments))
        app.post_message(MouseUp(**message_arguments))
        app.post_message(Click(**message_arguments))
    elif op == 'drag_release':
        app.post_message(MouseMove(**message_arguments))
        app.post_message(MouseUp(**message_arguments))
    else:
        app.post_message(cls(**message_arguments))
    await pilot.pause(0.01)


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


async def wait_for_idle(pilot, app: App | None = None):
    """Wait for the asyncio event loop to become idle."""
    def pump_is_idle(p):
        return not (
            not p._message_queue.empty() or p._pending_message
            or getattr(p, '_callbacks', None)
            or getattr(p, '_next_callbacks', None))

    loop = asyncio.get_running_loop()
    for i in range(100):
        pumps_are_idle = True
        if app:
            for p in all_pumps(app):
                if not pump_is_idle(p):
                    pumps_are_idle = False
                    break
        if loop.is_idle() and pumps_are_idle:
            break
        delay = 0 if i < 30 else 0.01                           # noqa: PLR2004
        await asyncio.sleep(delay)
    else:                                                    # pragma: no cover
        msg = 'Call to wait_for_idle: Never reached IDLE state'
        raise RuntimeError(msg)


class AppRunner:                 # pylint: disable=too-many-instance-attributes
    """Runs the Clippets application in a controlled manner.

    The app is run under the pytest asyncio loop.

    This 'steals' some code from Textual.

    :actions:
        A list of actions to perform. Each entry is a callable or a string that
        gets interpreted as described for the following examples:

        pause:0.2
            Pause for a short time.
        wait:0.2:EditorHasExited
            Wait for an given message  for a given amount of time. If the
            message is not received within the time period, the test fails.
        left:group-1
            Perform a left mouse button click on the widget with the ID
            'group-1'. The word before the colon identifies the button and
            any modifier keys. Button names are 'left', ;right', 'up' and
            'down. Modifiers are not yet supported.
        hover:group-1
            Simluate the mouse hovering over a widgget.
        f1
            Press the F1 key. Any action without a colon character is
            interpreted as a key tp be pressed.

        Callable actions are simply invoked without arguments and any return
        value is ignored. To allow for future extension, the retrun value
        should be ``None``.
    """

    logf = None

    def __init__(                                               # noqa: PLR0913
            self,
            snippet_file: TempTestFile,
            actions: list[str | Callable],
            *,
            test_mode: bool = True,
            options: list[str] | None = None,
            control_editor: bool = False):
        if self.__class__.logf is None:
            self.__class__.logf = log.Log('/tmp/test.log')
        options = options or []
        args = [snippet_file.name, *options]
        if test_mode:
            args.append('--sync-mode')
        self.app = core.Clippets(core.parse_args(args))
        self.msg_q = asyncio.Queue()
        self.actions = actions
        self.pilot = None
        self.exited = False
        self.svg = ''
        if control_editor:
            self.watch_file = TempTestFile()
            os.environ['CLIPPETS_TEST_WATCH_FILE'] = self.watch_file.name
        else:
            self.watch_file = None
            os.environ['CLIPPETS_TEST_WATCH_FILE'] = ''

    async def run(self, *, size: tuple = (80, 35)) -> str:
        """Run the application."""
        coro =  self.app.run_test(
            headless=True, size=size, message_hook=self.on_msg)
        tb = ''
        try:
            async with coro as self.pilot:
                await self.wait_for_message_name('Ready')
                with self.logf:
                    for action in self.actions:
                        await self.apply_action(action)
                    self.app.refresh()
                    await self.pilot._wait_for_screen()
                    self.app.screen._on_timer_update()
                if not self.svg:
                    self.svg = await self.take_screenshot()
                self.exited = self.app._exit
                await self.pilot.press('ctrl+c')
                if self.watch_file is not None:
                    self.watch_file.close()                  # pragma: no cover
                    assert False, 'Edit session was not stopperd.'
        # pylint: disable=broad-exception-caught
        except Exception as exc:                             # pragma: no cover
            tb = traceback.format_exception(exc)
        except SystemExit as exc:                            # pragma: no cover
            tb = traceback.format_exception(exc)
        return self.svg, tb, self.app._exit

    async def apply_action(self, action):
        """Apply an action."""
        if callable(action):
            action()
            return

        if len(action) > 2:                                     # noqa: PLR2004
            cmd, colon, arg = action.partition(':')
        else:
            cmd, colon, arg = action, '', ''
        if colon:
            await self.apply_cmd_action(cmd, arg)
        else:
            await self.pilot.press(action)
            await wait_for_idle(self.pilot, self.app)

    async def take_screenshot(self, timeout=1.0):
        """Take a screenshot, checking for stability.

        This creates multiple screen shots until two consecutive screens are
        the same or the operation times out.
        """
        svg = self.app.export_screenshot()
        end_time = time.time() + timeout
        while time.time() < end_time:
            await asyncio.sleep(0.02)
            new_svg = self.app.export_screenshot()
            if svg == new_svg:
                return svg
            svg = new_svg

        msg = 'Timed out waiting for stable screen shot'     # pragma: no cover
        raise RuntimeError(msg)                              # pragma: no cover

    async def exec_wait(self, arg):
        """Execute a wait action."""
        timeout, _, message_type_name = arg.partition(':')
        end_time = time.time() + float(timeout)
        while time.time() <= end_time:
            while not self.msg_q.empty():
                m = await self.msg_q.get()
                if m.__class__.__name__ == message_type_name:
                    return
            await asyncio.sleep(0.01)

        msg = f'Timed out waiting for {message_type_name}'   # pragma: no cover
        raise RuntimeError(msg)                              # pragma: no cover

    async def apply_cmd_action(self, cmd, arg):
        """Apply an action consisting of a command and argument(s)."""
        handler = getattr(self, f'exec_{cmd}', None)
        if handler:
            return await handler(arg)
        else:
            return await self.exec_generic(cmd, arg)

    @staticmethod
    async def exec_pause(arg):
        """Execute a pause action."""
        await asyncio.sleep(float(arg))

    async def exec_snapshot(self, arg):
        """Execute a snapshot action."""
        self.svg = await self.take_screenshot()

    async def exec_end_edit(self, arg):
        """Execute a end_edit action."""
        assert self.watch_file
        self.watch_file.close()
        self.watch_file = None

    async def exec_generic(self, cmd, arg):
        """Execute a generic action."""
        offset = Offset()
        arg, _, offset_str = arg.partition('+')
        x_str, _, y_str = offset_str.partition('x')
        if y_str:
            offset = Offset(int(x_str), int(y_str))
        selector = arg if arg.startswith('.') else f'#{arg}'
        try:
            self.app.screen.query_one(selector)
        except NoMatches:                                    # pragma: no cover
            msg = f'Bad widget ID: {arg!r}, screen={self.app.screen}\n'
            names = set()
            for node in self.app.screen.query(None):
                if node.id:
                    names.add(node.id)
            msg += 'Known names:\n    '
            msg += '\n    '.join(names)
            raise RuntimeError(msg) from None

        kw = {}
        while '-' in cmd:
            mod, _, cmd = cmd.partition('-')
            kw[mod] = True
        if cmd == 'hover':
            await self.pilot.hover(selector=selector)
        else:
            if cmd in ('drag_release', 'leftdown'):
                button = 'left'
            else:
                button = cmd
            print("CLICK", button, cmd)
            await click(
                self.pilot, button=button, op=cmd, selector=selector,
                offset=offset, **kw)
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
            # TODO: Can I make the value below 0.01?
            return sched_time >= 0.01                           # noqa: PLR2004
        else:
            return True


class AltEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy to use `AltEventLoop`."""

    _loop_factory = AltEventLoop


# Make our enhanced event loop available.
asyncio.set_event_loop_policy(AltEventLoopPolicy())
