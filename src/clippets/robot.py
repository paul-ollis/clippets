"""Support for automated execution of Clippets.

This is currently only used as an aid to document generation and testing.

Use for other purposes at your own risk ;)
"""
# ruff: noqa: SLF001
from __future__ import annotations

import asyncio
import sys
import threading
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, TYPE_CHECKING, cast

from textual._context import (
    active_message_pump, message_hook as message_hook_context_var)
from textual.css.query import NoMatches
from textual.events import (
    Click, Event, MouseDown, MouseMove, MouseScrollDown, MouseUp)
from textual.geometry import Offset
from textual.pilot import Pilot, _get_mouse_message_arguments
from textual.walk import walk_depth_first

from . import tasks
from .platform import terminal_title

if TYPE_CHECKING:
    import argparse
    from collections.abc import AsyncGenerator

    from textual.app import App
    from textual.message import Message
    from textual.widget import Widget

if sys.platform.startswith('win32'):
    NativeEventLoop = asyncio.ProactorEventLoop    # type: ignore[attr-defined]
else:
    NativeEventLoop = asyncio.SelectorEventLoop

NULL_OFFSET = Offset()


class AppRunner:
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

    def __init__(                                               # noqa: PLR0913
            self,
            snippet_file: str,
            actions: list[str | Callable],
            *,
            test_mode: bool = True,
            options: list[str] | None = None,
            make_app: Callable[[list[str]], App],
        ):
        options = options or []
        args = [str(snippet_file), *options]
        if test_mode:
            args.append('--sync-mode')
        self.app = make_app(args)
        self.msg_q: asyncio.Queue = asyncio.Queue()
        self.actions = actions
        self.pilot: Pilot = Pilot(self.app)
        self.exited = False
        self.svg = ''

    async def run(self, *, size: tuple[int, int] = (80, 34)) -> tuple:
        """Run the application."""
        task = tasks.create_task(self._run(size=size))
        return await task

    async def _run(self, *, size: tuple[int, int] = (80, 34)) -> tuple:
        coro =  self.run_test(
            headless=True, size=size, message_hook=self.on_msg)
        tb = []
        try:
            async with coro as self.pilot:
                pilot = cast(Pilot, self.pilot)
                await self.wait_for_message_name('Ready')
                for action in self.actions:
                    await self.apply_action(action)
                self.app.refresh()
                await pilot._wait_for_screen()
                self.app.screen._on_timer_update()
                if not self.svg:
                    self.svg = await self.take_screenshot()
                self.exited = self.app._exit
                await pilot.press('ctrl+c')
                self.clean_up()

        # pylint: disable=broad-exception-caught
        except Exception as exc:                                 # noqa: BLE001
            tb = traceback.format_exception(exc)
        except SystemExit as exc:
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
            await wait_for_idle(self.app)

    @asynccontextmanager
    async def run_test(                                         # noqa: PLR0913
        self,
        *,
        headless: bool = True,
        size: tuple[int, int] | None = (80, 24),
        tooltips: bool = False,
        notifications: bool = False,
        message_hook: Callable[[Message], None] | None = None,
    ) -> AsyncGenerator[Pilot, None]:
        """Run app under test conditions.

        Use this to run your app in "headless" (no output) mode and driver the
        app via a [Pilot][textual.pilot.Pilot] object.

        Example:
            ```python
            async with app.run_test() as pilot:
                await pilot.click("#Button.ok")
                assert ...
            ```

        Args:
            headless: Run in headless mode (no output or input).
            size: Force terminal size to `(WIDTH, HEIGHT)`,
                or None to auto-detect.
            tooltips: Enable tooltips when testing.
            message_hook:
                An optional callback that will called with every message going
                through the app.
        """
        app = self.app
        app._disable_tooltips = not tooltips
        app_ready_event = asyncio.Event()

        def on_app_ready() -> None:
            """Note when app is ready to process events."""
            app_ready_event.set()

        async def run_app(app) -> None:
            """Run the application."""
            if message_hook is not None:
                message_hook_context_var.set(message_hook)
            app._loop = asyncio.get_running_loop()
            app._thread_id = threading.get_ident()
            await app._process_messages(
                ready_callback=on_app_ready,
                headless=headless,
                terminal_size=size,
            )

        # Launch the app in the "background"
        active_message_pump.set(app)
        app_task = tasks.create_task(run_app(app), name=f'run_test {app}')

        # Wait until the app has performed all startup routines.
        await app_ready_event.wait()

        # Get the app in an active state.
        app._set_active()

        # Context manager returns pilot object to manipulate the app
        try:
            with terminal_title('Snippet-wrangler'):
                pilot = Pilot(app)
                await pilot._wait_for_screen()
                yield pilot
        finally:
            # Shutdown the app cleanly
            await app._shutdown()
            await app_task
            # Re-raise the exception which caused panic so test frameworks are
            # aware
            if self.app._exception:
                raise self.app._exception

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

        msg = 'Timed out waiting for stable screen shot'
        raise RuntimeError(msg)

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

        msg = f'Timed out waiting for {message_type_name}'
        raise RuntimeError(msg)

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
        except NoMatches:
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
            button = 'left' if cmd in ('drag_release', 'leftdown') else cmd
            await click(
                self.pilot, button=button, op=cmd, selector=selector,
                offset=offset, **kw)
        await wait_for_idle(self.app)

    def on_msg(self, m):
        """Handle a message generated by the app."""
        self.msg_q.put_nowait(m)

    async def wait_for_message_name(self, name: str):
        """Wait for a given application message."""
        while True:
            m = await self.msg_q.get()
            if m.__class__.__name__ == name:
                break

    def clean_up(self) -> None:
        """Perform post-run clean up."""


def run_capture(
        args: argparse.Namespace,
        make_app: Callable[[list[str]], App]):
    """Run Clippets and capture the output in an SVG file.

    :args:
        The parsed arguments.
    :make_app:
        A function that will create the Clippets application instance.
    """
    # Actions can be in a '.prog' file named after the snippet file or they can
    # be embedded in comments within the snippet file. The snippet file can
    # also contain:
    #
    # - The required dimensions.
    # - The height of the clipboard view area.
    dims = [80, 30]
    view_height: int | None = None
    actions = []
    prog = args.snippet_file.parent / f'{args.snippet_file.stem}.prog'
    if prog.exists():
        actions = args.prog.read_text().strip().splitlines()
    elif args.snippet_file.exists():
        extracting = False
        for rawline in args.snippet_file.read_text().splitlines():
            line = rawline.strip()
            if line == '# Prog':
                extracting = True
            elif line == '# End Prog':
                extracting = False
            elif line.startswith('# Dims: '):
                new_dims = [int(s) for s in line[8:].split('x')]
                if len(new_dims) == 2:
                    dims = [max(40, new_dims[0]), max(10, new_dims[1])]
            elif line.startswith('# ViewHeight: '):
                view_height = int(line[13:].strip())
            elif line.startswith('# '):
                actions.append(line[2:].strip())

    options = ['--svg-run']
    if view_height:
        options.append(f'--view-height={view_height}')
    runner = AppRunner(
        snippet_file=args.snippet_file,
        actions=actions,
        test_mode=True,
        options=options,
        make_app=make_app,
    )
    if args.dims:
        dims = [int(s) for s in args.dims.split('x')]
    svg, tb, *_ = asyncio.run(runner.run(size=dims))
    if tb:
        print(''.join(tb), file=sys.__stdout__)

    # Load any SVG overlay file.
    overlay = args.svg.parent / f'{args.svg.stem}.ovl'
    if overlay.exists():
        overlay_lines = overlay.read_text().splitlines()
        body_idx = -1
        x, y = [0.0, 0.0]
        for i, line in enumerate(overlay_lines):
            if line.strip() == '[[[BODY]]]':
                body_idx = i
            elif line.strip().startswith('transform="translate('):
                _, _, a = line.partition('(')
                a, _, _ = a.partition(')')
                x, y = [float(s) for s in a.split(',')]

    # Textual puts the title string on title bar of the terminal image, which
    # looks odd when it is also displayed in the Clippets title bar. Hence this
    # code to chop it out.
    lines = svg.splitlines()
    for i, line in enumerate(lines):
        if line.startswith('    <rect fill="#292929" stroke='):
            idx = line.find('<text ')
            if idx > 0:
                line = line[:idx]
                if overlay.exists():
                    line = line.replace('x="1"', f'x="{x}"')
                lines[i] = line
                break

    # Merge the SVG with any overlay file.
    overlay = args.svg.parent / f'{args.svg.stem}.ovl'
    if overlay.exists():
        for i, line in enumerate(lines):
            if 'transform="translate(' in line:
                a, _, r = line.partition('(')
                v, _, b = r.partition(')')
                xx, yy = [float(s) for s in v.split(',')]
                lines[i] = f'{a}({xx + x}, {yy + y}){b}'

        overlay_lines[body_idx:body_idx+1] = lines[1:-1]
        lines = overlay_lines

    with args.svg.open(mode='w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


async def wait_for_idle(app: App | None = None):
    """Wait for the asyncio event loop to become idle."""
    def pump_is_idle(p):
        return not (
            not p._message_queue.empty() or p._pending_message
            or getattr(p, '_callbacks', None)
            or getattr(p, '_next_callbacks', None))

    loop = cast(AltEventLoop, asyncio.get_running_loop())
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
    else:
        msg = 'Call to wait_for_idle: Never reached IDLE state'
        raise RuntimeError(msg)


def all_pumps(app: App):
    """Iterate over all (active) message pumps."""
    yield app
    yield from walk_depth_first(app.screen)


async def click(                                                # noqa: PLR0913
    pilot,
    *,
    button: str,
    op: str,
    selector: type[Widget] | str | None = None,
    offset: Offset = NULL_OFFSET,
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
    app = pilot.app
    screen = app.screen
    target_widget = screen.query_one(selector)

    cls: type[Event] = Click
    bn = 0
    if op == 'drag_release':
        cls = MouseMove
    elif op == 'leftdown':
        cls = MouseDown
    if button in ('left', 'right'):
        bn = 1 if button == 'left' else 3
    elif button == 'down':
        cls = MouseScrollDown
    else:
        msg = f'Mouse button name {button!r} is invalid'
        raise RuntimeError(msg)
    message_arguments = _get_mouse_message_arguments(
        target_widget, offset, button=bn, shift=shift, meta=meta,
        control=control,
    )
    await wait_for_idle()
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


class AltEventLoop(NativeEventLoop):
    """This wrapping of the event loop to allow idle detection."""

    _ready: bool
    _clock_resolution: float
    _scheduled: list[asyncio.TimerHandle]

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
            sched_time = self._scheduled[0].when() - end_time
            # TODO: Can I make the value below 0.01?
            return sched_time >= 0.01                           # noqa: PLR2004
        else:
            return True


class AltEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy to use `AltEventLoop`."""

    _loop_factory = AltEventLoop


# Make our enhanced event loop available.
asyncio.set_event_loop_policy(AltEventLoopPolicy())
