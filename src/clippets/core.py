"""Program to allow efficient composition of text snippets."""
# pylint: disable=too-many-lines

# 3. A user guide will be needed if this is to be made available to others.
# 6. Global keywords?
# 8. Make it work on Macs.
# 10. Generate frozen versions for all platforms.

# TODO: Make terminology consistent as follows.
#       Added
#           A snippet that has been added to the clipboard.
#       Selected
#           The snippet that has the box around. Many actions operate on this
#           snippet. This is stored as the snippet ID and can be ``None`` when
#           no snippet is present or visible.
#       Focussed
#           This should only relate to the filter input.

from __future__ import annotations

import argparse
import asyncio
import itertools
import re
import subprocess
import sys
import threading
import time
from collections import deque
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from functools import partial, wraps
from pathlib import Path
from typing import (
    AsyncGenerator, Callable, ClassVar, Iterable, Iterator, TYPE_CHECKING,
    Union, cast)

from rich.syntax import Syntax
from rich.text import Text
from textual._context import (
    active_message_pump, message_hook as message_hook_context_var)
from textual.app import App, Binding, ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.message import Message
from textual.pilot import Pilot
from textual.screen import Screen
from textual.walk import walk_depth_first
from textual.widgets import Header, Input, Static
from textual.widgets._markdown import MarkdownFence

from . import markup, snippets
from .editor import TextArea
from .platform import (
    SharedTempFile, dump_clipboard, get_editor_command, get_winpos,
    put_to_clipboard, terminal_title)
from .snippets import (
    CannotMove, DefaultLoader, Group, GroupChild, GroupInsertionPointer,
    Loader, MarkdownSnippet, PlaceHolder, Root, Snippet,
    SnippetInsertionPointer, is_group, is_group_child, is_snippet,
    is_snippet_like)
from .widgets import (
    DefaulFileMenu, FileChangedMenu, GreyoutScreen, GroupMenu, GroupNameMenu,
    MyFooter, MyInput, MyLabel, MyMarkdown, MyTag, MyText, MyVerticalScroll,
    SnippetMenu)

from . import patches                                              # noqa: F401

if TYPE_CHECKING:
    from textual.binding import _Bindings
    from textual.timer import Timer
    from textual.widget import Widget

HL_GROUP = ''
LEFT_MOUSE_BUTTON = 1
RIGHT_MOUSE_BUTTON = 3
BANNER = r'''
  ____ _ _                  _
 / ___| (_)_ __  _ __   ___| |_ ___
| |   | | | '_ \| '_ \ / _ \ __/ __|
| |___| | | |_) | |_) |  __/ |_\__ \
 \____|_|_| .__/| .__/ \___|\__|___/
          |_|   |_|
'''
DEFAULT_CONTENTS = '''
Main
  @md@
    My first snippet.
  @md@
    My second snippet.
Second
  @md@
    My third snippet.
'''.strip()

SnippetWidget = Union[MyMarkdown, MyText, Static]
Pointer = Union[SnippetInsertionPointer, GroupInsertionPointer]


class StartupError(Exception):
    """Error raised when Clippets cannot start."""


def only_in_context(name: str):
    """Wrap Smippets method to only run when in a given context."""
    def decor(method):
        @wraps(method)
        def invoke(self, *args, **kwargs):
            if self.context_name() == name:
                return method(self, *args, **kwargs)
            else:
                return None                                  # pragma: no cover
        return invoke

    return decor


@dataclass
class Selection:
    """Information about a widget selection.

    @uid:    The ID of the slected widget.
    @user: True if the user manually made the selection.
    """

    uid: str
    user: bool

    def __repr__(self):
        mode = 'user' if self.user else 'auto'
        return f'Sel-{mode}:{self.uid}'


class SetupDefaultFile(Message):
    """An inidication that we need to create a default file."""


class EditorHasExited(Message):
    """An inidication the extenal editor has exited."""


class Matcher:                         # pylint: disable=too-few-public-methods
    """Simple plain-text replacement for a compiled regular expression."""

    def __init__(self, pat: str):
        self.pat = pat.casefold()

    def search(self, text: str) -> bool:
        """Search for plain text."""
        return not self.pat or self.pat in text.lower()


class EditorScreen(Screen):
    """An internal editor."""

    _inherit_bindings: ClassVar[bool] = False
    preview: MyMarkdown

    def __init__(self, text: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text = text
        self._prev_lines: list[str] = []

    def compose(self) -> ComposeResult:
        """Build the widget tree for the editor screen."""
        yield Header(id='header')
        vs = MyVerticalScroll(id='editor_view_sc', classes='editor_result')
        vs.can_focus = False
        vs.can_focus_children = False
        vs.border_title = 'Rendered output'
        with vs:
            self.preview = MyMarkdown(id='result')
            self.preview.can_focus = False
            self.preview.can_focus_children = False
            yield self.preview
        ta =  TextArea(
            on_changed=self.on_changed, id='editor_sc',classes='editor_sc')
        ta.border_title = 'Edit area'
        yield ta
        yield MyFooter()

    def on_mount(self):
        """Tada."""
        ta = self.query_one(TextArea)
        ta.lines = self.text.splitlines()
        ta.focus()

    def on_changed(self, lines):
        """Handle change to the editor contents."""
        if lines != self._prev_lines:
            self.preview.update('\n'.join(lines))
            self._prev_lines[:] = lines


class HelpScreen(Screen):
    """The screen that is used to display help."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        """Build the widget tree for the editor screen."""
        yield Header(id='header')
        yield Static(BANNER, classes='banner')
        yield from markup.generate()
        yield MyFooter()

    def on_screen_resume(self):
        """Fix code block styling as soon as possible."""
        fences = (
            f for f in walk_depth_first(self) if isinstance(f, MarkdownFence))
        statics = (
            cast(Static, c) for ff in fences
            for c in walk_depth_first(ff) if c.__class__ is Static)

        for cc in statics:
            if isinstance(cc.renderable, Syntax):
                cc.renderable.padding = 0, 0, 0, 0
                cc.renderable.indent_guides = False


class MainScreen(Screen):
    """Main Clippets screen."""

    tag_id_sources: ClassVar[dict[str, itertools.count]] = {}
    app: Clippets

    def __init__(self, root: Root, uid: str):
        super().__init__(name='main', id=uid)
        self.root = root
        self.walk = root.walk
        self.widgets: dict[str, Widget] = {}

    def compose(self) -> ComposeResult:
        """Build the widget hierarchy."""
        yield Header()

        with Horizontal(id='input', classes='input oneline'):
            yield MyLabel('Filter: ')
            inp = MyInput(placeholder='Enter text to filter.', id='filter')
            inp.cursor_blink = False
            yield inp
        with MyVerticalScroll(id='view', classes='result'):
            if self.app.args.raw:
                yield Static(id='result')
            else:
                yield MyMarkdown(id='result')
        with MyVerticalScroll(id='snippet-list', classes='bbb'):
            yield from self.build_tree_part()
        footer = MyFooter()
        footer.add_class('footer')
        yield footer

    def build_tree_part(self):
        """Yield widgets for the tree part of the UI."""
        self.widgets = {}
        all_tags = {
            t: i for i, t in enumerate(sorted(Group.all_tags))}
        for el in self.walk(predicate=is_display_node):
            el.dirty = True
            uid = el.uid()
            if isinstance(el, Group):
                classes = 'is_group'
                label = MyLabel(
                    f'▽ {HL_GROUP}{el.name}', id=uid, classes=classes)
                fields = []
                for tag in el.tags:
                    classes = f'tag_{all_tags[tag]}'
                    fields.append(MyTag(
                        f'{tag}', id=self.gen_tag_id(tag), name=tag,
                        classes=f'tag {classes}'))
                w = Horizontal(label, *fields, classes='group_row')
                w.styles.margin = 0, 0, 0, (el.depth() - 1) * 4
                self.widgets[uid] = w
                yield w
            else:
                snippet = make_snippet_widget(uid, el)
                if snippet:
                    self.widgets[uid] = snippet
                    yield snippet

    def rebuild_tree_part(self):
        """Rebuild the tree part of the UI."""
        top = self.query_one('#snippet-list')
        top.remove_children()
        top.mount(*self.build_tree_part())

    def on_idle(self):
        """Perform idle processing."""
        w = cast(MyFooter, self.query_one('.footer'))
        w.check_context()

    def gen_tag_id(self, tag: str) -> str:
        """Generate a unique widget ID for a tag."""
        if tag not in self.tag_id_sources:
            self.tag_id_sources[tag] = itertools.count()
        return f'tag-{tag}-{next(self.tag_id_sources[tag])}'

    def lookup_widget(self, el):
        """Find the widget for a given element.

        This is only valid for the MainScreen widgets.
        """
        return self.widgets.get(el.uid())

    def on_screen_resume(self):
        """Handle when this screen is resumed."""
        self.screen.set_focus(None)


def make_snippet_widget(uid, snippet) -> Widget | None:
    """Construct correct widegt for a given snnippet."""
    classes = 'is_snippet'
    w: MyMarkdown | MyText | Static | None = None
    if isinstance(snippet, MarkdownSnippet):
        w = MyMarkdown(id=uid, classes=classes)
    elif isinstance(snippet, Snippet):
        classes = f'{classes} is_text'
        w = MyText(id=uid, classes=classes)
    elif isinstance(snippet, PlaceHolder):
        classes = f'{classes} is_placehoder'
        w = Static('-- place holder --', id=uid, classes=classes)
        w.display = False
    if w:
        w.styles.margin = 0, 1, 0, (snippet.depth() - 1) * 4
    return w


async def populate(q, walk, query):
    """Background task to populate widgets."""
    yield_period = 0.01
    sleep_period = 0.01

    while True:
        while q.qsize() > 1:
            cmd = await q.get()                              # pragma: no cover
        cmd = await q.get()
        if cmd is None:
            break

        a = time.time()
        for snippet in walk():
            if q.qsize() > 0:
                break                                        # pragma: no cover
            if snippet.dirty:
                w = query(snippet)
                if w is not None:
                    w.update(snippet.marked_text)
                    snippet.dirty = False
                    if (time.time() - a) >= yield_period:
                        await asyncio.sleep(sleep_period)
                        a = time.time()


def populate_fg(walk, query):
    """Populate widgets."""
    for snippet in walk():
        if snippet.dirty:
            w = query(snippet)
            if w is not None:
                w.update(snippet.marked_text)
                snippet.dirty = False


async def resolve(q, lookup, walk, query):
    """Background task to resolve widgets to element mapping."""
    while True:
        while q.qsize() > 1:
            cmd = await q.get()                              # pragma: no cover
        cmd = await q.get()
        if cmd is None:
            break

        new_lookup = {}
        elements = list(walk())
        for el in elements:
            if q.qsize() > 0:
                break                                        # pragma: no cover
            uid = el.uid()
            if uid and uid not in new_lookup:
                with suppress(NoMatches):
                    new_lookup[uid] = query(f'#{uid}')
                    await asyncio.sleep(0.01)
        else:
            if q.qsize() == 0:
                lookup.clear()
                lookup.update(new_lookup)


class EditSession:
    """Encapsulation of a user editing session."""

    def __init__(
            self,
            app: Clippets,
            on_complete: Callable[[str], None]):
        self.app = app
        self.on_complete = on_complete

    def save(self):
        """Save the changes from the editor."""
        ta = self.app.query_one('TextArea')
        text = '\n'.join(ta.lines)
        self.app.pop_screen()
        self.app.edit_session = None
        self.on_complete(text)

    def quit(self):                                                # noqa: A003
        """Quite the editor."""
        self.app.pop_screen()
        self.app.edit_session = None


class ExtEditSession(EditSession):
    """Encapsulation of an external editing session."""

    def __init__(
            self,
            app: Clippets,
            temp_path: SharedTempFile,
            proc: asyncio.subprocess.Process |None,
            on_complete: Callable[[str], None]):
        super().__init__(app, on_complete)
        self.temp_path = temp_path
        self.proc = proc
        self.timer: Timer = app.set_interval(0.02, self.check_if_edit_finished)

    async def check_if_edit_finished(self):
        """Poll to see if the editor process has finished."""
        if self.proc and self.proc.returncode is not None:
            # Note that more calls to this method may already be queued. We
            # cannot rely on simply stopping the timer. So we use self.proc
            # being ``None`` as a guard.
            proc, self.proc = self.proc, None

            self.timer.stop()
            await proc.wait()
            text = self.temp_path.read_text(encoding='utf8')
            self.temp_path.clean_up()
            self.app.pop_screen()
            self.on_complete(text)
            self.app.edit_session = None
            self.app.post_message(EditorHasExited())


class AppMixin:
    """Mixin providing application logic."""

    # pylint: disable=too-many-public-methods
    # pylint: disable=too-many-instance-attributes
    args: argparse.Namespace
    focused: Widget
    mount: Callable
    pop_screen: Callable
    push_screen: Callable
    query_one: Callable
    resolver: asyncio.Task | None
    screen: Screen
    context_name: Callable[[], str]
    _bindings: _Bindings
    MODES: ClassVar[dict[str, str | Screen | Callable[[], Screen]]]

    def __init__(self, root: Root):
        super().__init__()
        for name in list(self.MODES):
            if name != '_default':
                self.MODES.pop(name)
        self.added: list[str] = []
        self.collapsed: set[str] = set()
        self.edited_text = ''
        self.filter: re.Pattern | Matcher = Matcher('')
        self.root = root
        self.hover_uid = None
        first_el = self.root.first_snippet() or self.root.first_group()
        self._selection_stack = [Selection(uid=first_el.uid(), user=False)]
        self.pointer: Pointer | None = None
        self.hidden_snippets: set[Widget] = set()
        self.redo_buffer: deque = deque(maxlen=20)
        self.sel_order = False
        self.undo_buffer: deque = deque(maxlen=20)
        self.lookup: dict[str, Widget] = {}
        self.walk = root.walk
        self.resolver_q: asyncio.Queue = asyncio.Queue()
        self.populater_q: asyncio.Queue = asyncio.Queue()
        self.walk_snippet_like = partial(self.walk, is_snippet_like)
        self.populater: asyncio.Task | None = None
        self.edit_session: EditSession | None = None
        self.disabled_bindings: dict[str, Binding] = {}

    async def on_exit_app(self, _event):
        """Clean up when exiting the application."""
        if self.populater:
            self.populater_q.put_nowait(None)
            await self.populater

    @property
    def selection_uid(self) -> str:
        """The UID of the currently selected group or snippet."""
        return self._selection_stack[-1].uid

    @property
    def selection(self) -> tuple[GroupChild, Widget] | tuple[None, None]:
        """The currently selected element and widget."""
        el_id = self._selection_stack[-1].uid
        el = self.root.find_group_child(el_id)
        if el is not None:
            return el, self.find_widget(el)
        else:
            return None, None

    @only_in_context('normal')
    def handle_blur(self, w: Widget):
        """Handle loss of focus for a widget.

        Currernly this only occurs for the filter input widget.
        """
        w.remove_class('kb_focussed')
        self.set_visuals()

    def find_widget_by_uid(self, uid: str) -> Widget:
        """Find the widget for a given element."""
        if uid not in self.lookup:
            self.lookup[uid] = self.query_one(f'#{uid}')
        return self.lookup[uid]

    def find_widget(self, el) -> Widget:
        """Find the widget for a given element."""
        return self.find_widget_by_uid(el.uid())

    def walk_snippet_widgets(self) -> Iterator[Widget]:
        """Iterate over of the tree of Snippet widgets."""
        for el in self.walk(predicate=is_snippet):
            yield self.find_widget(el)

    def walk_group_widgets(self) -> Iterator[Widget]:
        """Iterate over of the tree of Snippet widgets."""
        for el in self.walk(predicate=is_group):
            yield self.find_widget(el)

    ## Management of dynanmic display features.
    def set_visuals(self) -> None:
        """Set and clear widget classes that control visual highlighting."""
        self.set_snippet_visuals()
        self.set_input_visuals()

    @staticmethod
    def _clear_move_marker( el, w):
        if isinstance(el, Group):
            w.parent.remove_class('dest_above')
            w.parent.remove_class('dest_below')
        else:
            w.remove_class('dest_above')
            w.remove_class('dest_below')

    @staticmethod
    def _set_move_marker(source, dest, w):
        uid, after = dest.addr
        if uid != source.uid() and uid == w.id:
            if isinstance(dest.child, Group):
                w.parent.add_class('dest_below' if after else 'dest_above')
            else:
                if isinstance(dest.child, PlaceHolder):
                    after = False
                w.add_class('dest_below' if after else 'dest_above')
            if isinstance(dest.child, PlaceHolder):
                w.display = True

    def set_snippet_visuals(self) -> None:
        """Set and clear widget classes that control snippet highlighting."""
        filter_focussed = (fw := self.focused) and fw.id == 'filter'
        _, selected_widget = self.selection
        for el in self.walk(predicate=is_display_node):
            w = self.find_widget(el)
            w.remove_class('kb_focussed')
            w.remove_class('mouse_hover')
            self._clear_move_marker(el, w)
            if isinstance(el, PlaceHolder):
                w.display = False
            p = self.pointer
            if p is not None:
                if w.id != p.source.uid():
                    self._set_move_marker(p.source, p, w)
            else:
                if w == selected_widget and not filter_focussed:
                    w.add_class('kb_focussed')
                if w.id == self.hover_uid:
                    w.add_class('mouse_hover')

    def set_input_visuals(self) -> None:
        """Set and clear widget classes that control input highlighting."""
        filter_focussed = (fw := self.focused) and fw.id == 'filter'
        w = self.query_one('#input')
        if filter_focussed:
            w.add_class('kb_focussed')
        else:
            w.remove_class('kb_focussed')

    def update_selected(self) -> None:
        """Update the 'selected' flag following mouse movement."""
        for snippet in self.walk(predicate=is_snippet):
            id_str = snippet.uid()
            w = self.find_widget(snippet)
            if id_str in self.added:
                w.add_class('selected')
            else:
                w.remove_class('selected')

    ## Handling of mouse operations.
    async def on_click(self, ev) -> None:                          # noqa: C901
        """Process a mouse click."""
        if self.context_name() == 'normal':
            if ev.button == LEFT_MOUSE_BUTTON:
                if ev.meta:
                    w = getattr(ev, 'widget', None)
                    if w:
                        element = self.root.find_group_child(w.id)
                        if element:
                            self.action_start_moving_element(element.uid())
                elif not ev.meta:
                    self.on_left_click(ev)
            elif ev.button == RIGHT_MOUSE_BUTTON and not ev.meta:
                await self.on_right_click(ev)

        if ev.meta and ev.button == RIGHT_MOUSE_BUTTON:      # pragma: no cover
            # This is useful for debugging.
            w = getattr(ev, 'widget', None)
            if w:
                s = [f'Click: {w.id}']
                for name, value in w.styles.__rich_repr__():
                    s.append(f'    {name}={value}')
                s.append(f'    classes={w.classes}')

                ww = w.parent
                if ww:
                    s.append(f'  {ww}')
                    for name, value in ww.styles.__rich_repr__():
                        s.append(f'    {name}={value}')
                    s.append(f'    classes={ww.classes}')
                print('\n'.join(s))

    def on_left_click(self, ev) -> None:
        """Process a mouse left-click."""
        w = getattr(ev, 'widget', None)
        if w is None:
            return                                           # pragma: no cover

        id_str = w.id
        el = self.root.find_group_child(id_str)
        if isinstance(el, Snippet):
            self.push_undo()
            if id_str in self.added:
                self.added.remove(id_str)
            else:
                self.added.append(id_str)
            self.update_selected()
            self.update_result()

        elif isinstance(el, Group):
            if id_str in self.collapsed:
                self.collapsed.remove(id_str)
            else:
                self.collapsed.add(id_str)
            self.filter_view()

        elif isinstance(w, MyTag):
            self.action_toggle_tag(w.name)

    async def on_right_click(self, ev) -> None:
        """Process a mouse right-click."""
        w = getattr(ev, 'widget', None)
        if w is None:
            return                                           # pragma: no cover

        id_str = w.id
        el = self.root.find_group_child(id_str)
        if isinstance(el, Snippet):
            await self.on_right_click_snippet(w)
        elif isinstance(el, Group):
            await self.on_right_click_group(w)

    async def on_right_click_group(self, w: Widget) -> None:
        """Handle a mouse right-click on a group."""
        async def on_close(v):
            self.screen.set_focus(None)
            if  v == 'add_snippet':
                await self.add_snippet(wid)
            elif  v == 'add_group':
                await self.add_group(wid)
            elif  v == 'rename_group':
                await self.rename_group(wid)

        wid = cast(str, w.id)
        snippet = self.root.find_group_child(wid)
        if snippet:
            self.push_screen(GroupMenu(id='snippet-menu'), on_close)

    async def on_right_click_snippet(self, w: Widget) -> None:
        """Process a mouse right-click on a snippet."""

        async def on_close(v):
            self.screen.set_focus(None)
            if  v == 'add_snippet':
                await self.add_snippet(wid)
            elif  v == 'edit':
                await self.edit_snippet(wid)
            elif  v == 'duplicate':
                await self.duplicate_snippet(wid)
            elif  v == 'move':
                self.action_start_moving_element(wid)

        wid = cast(str, w.id)
        snippet = self.root.find_group_child(wid)
        if snippet:
            self.push_screen(SnippetMenu(id='snippet-menu'), on_close)

    ## Handling of keyboard operations.
    def fix_selection(self, *, kill_filter: bool = False):
        """Update the keyboard selected focus when widgets get hidden."""
        # Do nothing if the filter input is focused and should remain so.
        sel = self._selection_stack[-1]
        if sel.uid == 'filter':
            if kill_filter:
                self._selection_stack.pop()
            else:
                return

        # If the top of the stack is a group and the user moved there, do
        # nothing.
        if sel.uid.startswith('group-') and sel.user:
            return

        # If there is selection history (from previous fix-ups) try to reselect
        # the oldest entry in the history.
        for i, sel in enumerate(self._selection_stack):
            wid = sel.uid
            if i > 0 and wid is not None:
                w = self.query_one(f'#{wid}')
                if w.display:
                    self._selection_stack[:] = self._selection_stack[:i]
                    self.set_visuals()
                    self.screen.set_focus(None)
                    return

        # The selection history could not be used so find the best alternative
        # snippet to select, saving the currently selection in the history.
        self.action_select_move(inc=0)

    def action_select_move(
            self, inc: int, mode: str ='vertically', *, push: bool = False,
            user: bool = True,
        ) -> bool:
        """Move the selection up, down, left or right.

        Special behaviour occurs if inc is zero.

        - no movement will occur if the currentl selection is valid.
        - If the current selection is invalid then a value of inc=-1 is
          tried and if that fails then inc=1 is tried.
        - If neither adjustment works then (inc=-1, mode='horizontally') is
          used, which is guaranteed to work.

        :inc:  -1 => move left or up, 1 => move right or down and zero means
               stay put if possible.
        :mode: Must be either 'vertically' or 'horizontally'.
        :push: If set then push the new selection onto the selection stack.
               Otherwise replace the stack with the new selection.
        :user: If set then the user is making the move. Otherwise this move was
               triggered by an automatic adjustment.
        :return:
            True if a widget was succesffuly selected. When inc=0, the return
            value is guaranteed to be ``True``.
        """
        _, w = self.selection
        if w is None:
            # Selection has been broken. This can occur when a file reload
            # occurs.
            el: Group | Snippet | None = self.root.first_snippet()
            if el is None:
                el = self.root.first_group()
            w = self.find_widget(el)
            self._selection_stack[:] = [Selection(uid=el.uid(), user=False)]
            self.screen.set_focus(None)
            self.set_visuals()
            w.scroll_visible(animate=False)
            return True

        elif inc == 0:
            if w.display:
                return True
            else:
                move = partial(
                    self.action_select_move, push=True, mode=mode, user=False)
                to_group = partial(move, mode='horizontally')
                return move(-1) or move(1) or to_group(-1)

        elif mode == 'vertically':
            return self.select_move_vertically(inc, push=push, user=user)

        else:
            return self.select_move_horizontally(inc, user=user)

    def select_move_vertically(
            self, inc: int, *, push: bool = False, user: bool) -> bool:
        """Move the selection to the next available snippet.

        :inc:  -1 => move up, 1 => move down.
        :push: If set then push the new selection onto the selection stack.
               Otherwise replace the stack with the new selection.
        :user: If set then the user is making the move. Otherwise this move was
               triggered by an automatic adjustment.
        :return:
            True if a widget was succesffuly selected.
        """
        sel_id = self._selection_stack[-1].uid
        if sel_id and sel_id.startswith('group-'):
            return self.move_vertically_group_wise(inc, user=user)
        else:
            return self.move_vertically_snippet_wise(inc, push=push, user=user)

    def move_vertically_snippet_wise(
            self, inc: int, *, push: bool = False, user: bool) -> bool:
        """Move the snippet selection up or down.

        This may *only* be called when the current selection is a snippet.

        :inc:  -1 => move up, 1 => move down.
        :push: If set then push the new selection onto the selection stack.
               Otherwise replace the stack with the new selection.
        :user: If set then the user is making the move. Otherwise this move was
               triggered by an automatic adjustment.
        :return:
            True if a widget was succesffuly selected.
        """
        snippet, _ = self.selection
        if snippet is not None:
            for next_snippet in self.root.walk(
                    predicate=is_snippet, after=snippet, backwards=inc < 0):
                next_widget = self.find_widget(next_snippet)
                if next_widget.display:
                    if push:
                        self._selection_stack.append(
                            Selection(uid=next_snippet.uid(), user=user))
                    else:
                        self._selection_stack[:] = [
                            Selection(uid=next_snippet.uid(), user=user)]
                    self.screen.set_focus(None)
                    self.set_visuals()
                    next_widget.scroll_visible(animate=False)
                    return True

        return False

    def move_vertically_group_wise(self, inc: int, *, user: bool):
        """Move the group selection up or down.

        This may *only* be called when the current selection is a group.

        :inc:  -1 => move up, 1 => move down.
        :user: If set then the user is making the move. Otherwise this move was
               triggered by an automatic adjustment.
        :return:
            True if a widget was succesffuly selected.
        """
        sel_id = self._selection_stack[-1].uid
        group = cast(Group, self.root.find_group_child(sel_id))
        next_group = group.step_group(backwards=inc < 0)
        while next_group is not None:
            next_widget = self.find_widget(next_group)
            if next_widget.display:
                w = self.find_widget(next_group)
                self._selection_stack[-1] = Selection(
                    uid=next_group.uid(), user=user)
                self.set_visuals()
                w.scroll_visible(animate=False)
                return
            else:
                next_group = next_group.step_group(backwards=inc < 0)

    def select_move_horizontally(self, inc: int, *, user: bool):
        """Move the selection to/from group mode."""
        sel_id = self._selection_stack[-1].uid
        if inc == -1:
            if not sel_id.startswith('snippet-'):
                return
            group = cast(Group, self.root.find_group_child(sel_id)).parent
            self._selection_stack.append(
                Selection(uid=group.uid(), user=user))
            w = self.find_widget(group)
            self.set_visuals()
            w.scroll_visible(animate=False)
        else:
            if not sel_id.startswith('group-'):
                return
            group_id = self._selection_stack.pop().uid
            group = cast(Group, self.root.find_group_child(group_id))
            sel_id = self._selection_stack[-1].uid
            snippet = cast(Snippet, self.root.find_group_child(sel_id))
            if snippet.parent is not group:
                for snippet in group.snippets():
                    w = self.find_widget(snippet)
                    if w.display:
                        self._selection_stack[-1] = Selection(
                            uid=snippet.uid(), user=user)
                        break
                else:
                    # No snippet selectable in this gruop.
                    self._selection_stack.append(
                        Selection(uid=group_id, user=user))
                    return

            w = self.find_widget(snippet)
            self.set_visuals()
            w.scroll_visible(animate=False)

    ## Ways to limit visible snippets.
    def filter_view(self) -> None:
        """Hide snippets that have been filtered out or folded away."""
        def st_opened():
            return all(ste.uid() not in self.collapsed for ste in stack)

        def set_disp_if_changed(w: Widget, *, flag: bool):
            if w.display != flag:
                w.display = flag

        matcher = self.filter
        stack: list[GroupChild] = []
        opened = True
        for el in self.walk(predicate=is_group_child):
            if isinstance(el, Group):
                while stack and stack[-1].depth() >= el.depth():
                    stack.pop()
                w = cast(MyLabel, self.find_widget(el))
                w_parent = cast(MyLabel, w.parent)
                set_disp_if_changed(w, flag=st_opened())
                set_disp_if_changed(w_parent, flag=st_opened())

                opened = el.uid() not in self.collapsed
                if opened:
                    w.update(Text.from_markup(f'▽ {HL_GROUP}{el.name}'))
                else:
                    w.update(Text.from_markup(f'▶ {HL_GROUP}{el.name}'))

                stack.append(el)
                opened = st_opened()

            elif isinstance(el, Snippet):
                w_snippet = cast(SnippetWidget, self.find_widget(el))
                w_snippet.display = bool(matcher.search(el.text)) and opened
        self.fix_selection()
        self.ensure_selection_visible()

    ## UNCLASSIFIED
    def is_fully_collapsed(self):
        """Test whether all groups are collapsed."""
        groups = self.walk(predicate=is_group)
        return all(group.uid() in self.collapsed for group in groups)

    def is_fully_open(self, tag: str = ''):
        """Test whether all groups are open."""
        groups = self.walk(predicate=is_group)
        if tag:
            groups = (g for g in groups if tag in g.tags)
        return all(group.uid() not in self.collapsed for group in groups)

    def on_input_changed(self, message: Input.Changed) -> None:
        """Handle a change to the filter text input."""
        rexp: re.Pattern | Matcher
        if message.input.id == 'filter':
            pat = message.value
            if not pat.strip():
                rexp = Matcher('')
            else:
                try:
                    rexp = re.compile(f'(?i){pat}')
                except re.error:
                    rexp = Matcher(pat)
            self.filter = rexp
            self.filter_view()

    @only_in_context('normal')
    def update_hover(self, w) -> None:
        """Update the UI to indicate where the mouse is."""
        self.hover_uid = w.id
        self.set_visuals()

    def push_undo(self) -> None:
        """Save state onto the undo stack."""
        if self.edited_text:
            self.undo_buffer.append(([], self.edited_text))
        else:
            self.undo_buffer.append((list(self.added), ''))
        self.edited_text = ''

    ## Clipboard representaion widget management.
    def update_result(self) -> None:
        """Update the contents of the results display widget."""
        text = self.build_result_text()
        w = cast(Static, self.query_one('#result'))
        w.update(text)
        put_to_clipboard(
            text, mode='raw' if self.args.raw else 'styled')

    def build_result_text(self) -> str:
        """Build up the text that should be copied to the clipboard."""
        if self.edited_text:
            return self.edited_text

        s = []
        if self.sel_order:
            for id_str in self.added:
                snippet = cast(Snippet, self.root.find_group_child(id_str))
                s.extend(snippet.md_lines())
                s.append('')
        else:
            for snippet in self.walk(predicate=is_snippet):
                id_str = snippet.uid()
                if id_str in self.added:
                    s.extend(snippet.md_lines())
                    s.append('')
        if s:
            s.pop()
        return '\n'.join(s)

    ## Editing and duplicating snippets.
    async def add_group(self, id_str: str):
        """Add and the edit a new group."""

        async def on_close(v):
            self.screen.set_focus(None)
            if  v != 'cancel':
                new_group = group.parent.add_group(
                    screen.group_name, after=group.name)
                new_group.clean()
                self._selection_stack[-1:] = [
                    Selection(uid=new_group.uid(), user=True)]
                self.rebuild_after_edits()
                w = self.find_widget(new_group)
                w.scroll_visible(animate=False)

        if id_str.startswith('group-'):
            group = cast(Group, self.root.find_group_child(id_str))
            screen = GroupNameMenu(
                'Add group', self.root, id='add_group-dialog')
            self.push_screen(screen, on_close)

    async def add_snippet(self, id_str: str):
        """Add and the edit a new snippet."""

        def on_edit_complete(text):
            new_snippet.set_text(text)
            self._selection_stack[:] = [
                Selection(uid=new_snippet.uid(), user=True)]
            self.rebuild_after_edits()
            w = self.find_widget(new_snippet)
            w.scroll_visible(animate=False)

        if id_str.startswith('snippet-'):
            snippet = cast(Snippet, self.root.find_group_child(id_str))
            new_snippet = snippet.add_new()
        elif id_str.startswith('group-'):
            group = cast(Group, self.root.find_group_child(id_str))
            new_snippet = group.add_new()
        await self.run_editor(
            new_snippet.text, 'Currently editing a new snippet',
            on_edit_complete)

    def backup_and_save(self):
        """Create a new snippet file backup and then save."""
        snippets.backup_file(self.args.snippet_file)
        self.loader.save(self.root)                # type: ignore[attr-defined]

    async def duplicate_snippet(self, id_str: str):
        """Duplicate and the edit the current snippet."""

        def on_edit_complete(text):
            new_snippet.set_text(text)
            self._selection_stack[:] = [
                Selection(uid=new_snippet.uid(), user=True)]
            self.rebuild_after_edits()
            w = self.find_widget(new_snippet)
            w.scroll_visible(animate=False)

        if id_str.startswith('snippet-'):
            snippet = cast(Snippet, self.root.find_group_child(id_str))
            new_snippet = snippet.duplicate()
            await self.run_editor(
                new_snippet.text, 'Currently editing a duplicate snippet',
                on_edit_complete)

    async def edit_snippet(self, id_str) -> None:
        """Invoke the user's editor on a snippet."""

        def on_edit_complete(text):
            if text.strip() != snippet.text.strip():
                snippet.set_text(text)
                self.rebuild_after_edits()

        if id_str.startswith('snippet-'):
            snippet = cast(Snippet, self.root.find_group_child(id_str))
            await self.run_editor(
                snippet.text, 'Currently editing a snippet', on_edit_complete)

    def rebuild(self):
        """Rebuild, refresh, *etc*. after changes to the snippets tree."""
        self.lookup.clear()
        main_screen = cast(MainScreen, self.screen)
        main_screen.rebuild_tree_part()
        if self.resolver:
            self.resolver_q.put_nowait('rebuild')
        if self.populater:
            self.populater_q.put_nowait('pop')
        else:
            populate_fg(
                partial(self.walk, predicate=is_snippet),
                self.find_widget)

        self.update_result()
        self.filter_view()
        self.set_visuals()

    def rebuild_after_edits(self):
        """Rebuild, refresh, *etc*. after changes to the snippets tree."""
        self.backup_and_save()
        self.rebuild()

    async def run_editor(
            self, text: str, message: str,
            on_complete: Callable[[str], None]) -> None:
        """Run the user's preferred editor on a textual element."""
        ext_editor = get_editor_command('CLIPPETS_EDITOR', '')
        if ext_editor:
            self.push_screen(GreyoutScreen(message, id='greyout'))
            temp_path = SharedTempFile()
            proc = await run_editor(text, temp_path)
            self.edit_session = ExtEditSession(
                cast(Clippets, self), temp_path, proc, on_complete)
        else:
            self.disabled_bindings = self._bindings.keys.copy()
            self._bindings.keys.clear()
            self.push_screen(EditorScreen(text, id='editor'))
            self.edit_session = EditSession(
                cast(Clippets, self), on_complete)

    def action_edit_save_and_quit(self):
        """Save and quit an internal editor session."""
        if self.edit_session:
            self.edit_session.save()
            self._bindings.keys.update(self.disabled_bindings)

    def action_edit_quit(self):
        """Just quit an internal edirot session."""
        if self.edit_session:
            self.edit_session.quit()
            self._bindings.keys.update(self.disabled_bindings)

    async def rename_group(self, id_str: str):
        """Rename a group."""

        async def on_close(v):
            self.screen.set_focus(None)
            if  v != 'cancel' and screen.group_name != group.name:
                group.rename(screen.group_name)
                self.rebuild_after_edits()

        if id_str.startswith('group-'):
            group = cast(Group, self.root.find_group_child(id_str))
            screen = GroupNameMenu(
                'Add group', self.root, orig_name=group.name,
                id='add_group-dialog')
            self.push_screen(screen, on_close)

    ## Snippet position movement.
    def action_start_moving_element(self, id_str: str | None = None) -> None:
        """Start moving a group/snippet to a different position in the tree."""
        id_str = id_str or self.selection_uid
        w = self.query_one(f'#{id_str}')
        element = self.root.find_group_child(id_str)
        if isinstance(element, Snippet):
            self.start_moving_snippet(w, element)
        elif isinstance(element, Group):
            self.start_moving_group(w, element)

    def start_moving_snippet(self, sel_w: Widget, snippet: Snippet) -> None:
        """Start moving a snippet to a different position in the tree."""
        try:
            self.pointer = SnippetInsertionPointer(snippet)
        except CannotMove:
            return
        sel_w.add_class('moving')
        self.set_visuals()

    def start_moving_group(self, sel_w: Widget, group: Group) -> None:
        """Start moving a group to a different position in the tree."""
        sel_w.add_class('moving')
        try:
            self.pointer = GroupInsertionPointer(group)
        except CannotMove:
            return

        for w in self.walk_snippet_widgets():
            if w.display and isinstance(w.id, str):
                self.hidden_snippets.add(w)
                w.display = False
        for w in self.walk_group_widgets():
            container = cast(Horizontal, w.parent)
            top, right, _, left = container.styles.padding
            container.styles.padding = top, right, 1, left
        self.set_visuals()

    def ensure_selection_visible(self):
        """Make sure that the selected snippet/group is visible."""
        if self.selection_uid:
            w = self.find_widget_by_uid(self.selection_uid)
            w.scroll_visible(animate=False)

    ## Binding handlers.
    async def action_add_group(self) -> None:
        """Add and edit a new group."""
        if self.selection_uid:
            await self.add_group(self.selection_uid)

    async def action_add_snippet(self) -> None:
        """Add and edit the a new snippet."""
        if self.selection_uid:
            await self.add_snippet(self.selection_uid)

    def action_clear_selection(self) -> None:
        """Clear all snippets from the selection."""
        self.added[:] = []
        self.update_result()
        self.update_selected()

    def action_complete_move(self):
        """Complete a snippet move operation."""
        p = self.pointer
        self.action_stop_moving()
        if p and p.move_source():
            self.rebuild_after_edits()
            if p.source.uid().startswith('snippet-'):
                self._selection_stack[:] = [
                    Selection(uid=p.source.uid(), user=True)]
            self.set_visuals()

    def action_do_redo(self) -> None:
        """Redo the last undo action."""
        if self.redo_buffer:
            self.undo_buffer.append((self.added, self.edited_text))
            self.added, self.edited_text = self.redo_buffer.pop()
            self.update_result()
            self.update_selected()

    def action_do_undo(self) -> None:
        """Undo the last change."""
        if self.undo_buffer:
            self.redo_buffer.append((self.added, self.edited_text))
            self.added, self.edited_text = self.undo_buffer.pop()
            self.update_result()
            self.update_selected()

    async def action_duplicate_snippet(self) -> None:
        """Duplicate and edit the currently selected snippet."""
        await self.duplicate_snippet(self.selection_uid)

    async def action_edit_clipboard(self) -> None:
        """Run the user's editor on the current clipboard contents."""
        def on_edit_complete(new_text: str):
            if new_text.strip() != text.strip():
                self.edited_text = new_text
                self.update_result()

        text = self.build_result_text()
        self.push_undo()
        await self.run_editor(
            text, 'Currently editing clipboard contents', on_edit_complete)

    async def action_edit_keywords(self) -> None:
        """Invoke the user's editor on the current group's keyword list."""
        def on_edit_complete(new_text: str):
            new_words = set(new_text.split())
            if new_words != kw.words:
                kw.words = new_words
                self.backup_and_save()
                for snippet in self.walk(predicate=is_snippet):
                    snippet.reset()
                if self.populater:
                    self.populater_q.put_nowait('pop')
                else:                                        # pragma: no cover
                    populate_fg(
                        partial(self.walk, predicate=is_snippet),
                        self.find_widget)
                self.root.update_keywords()

        el, _ = self.selection
        group = cast(Group, el.parent if isinstance(el, Snippet) else el)
        kw = group.keyword_set
        await self.run_editor(
            kw.text, 'Currently editing group keywords', on_edit_complete)

    def action_enter_filter(self) -> None:
        """Move focus to the filter input field."""
        w = self.query_one('#filter')
        self.screen.set_focus(w)
        self._selection_stack.append(Selection(uid='filter', user=True))
        self.set_visuals()

    def action_leave_filter(self) -> None:
        """Move focus away from the filter input field."""
        self.screen.set_focus(None)
        self.fix_selection(kill_filter=True)
        self.set_visuals()

    async def action_edit_snippet(self) -> None:
        """Edit the currently selected snippet."""
        await self.edit_snippet(self.selection_uid)

    def action_move_insertion_point(self, direction: str) -> bool:
        """Move the snippet insertion up of down.

        :direction: Either 'up' or 'down'.
        """
        p = self.pointer
        if p is None:
            return False                                     # pragma: no cover

        if p.move(backwards=direction == 'up'):
            self.set_visuals()
            w = self.find_widget(p.child)
            w.scroll_visible(animate=False)
            return True
        else:
            return False

    async def action_rename_group(self) -> None:
        """Rename an existing group."""
        if self.selection_uid:
            await self.rename_group(self.selection_uid)

    def action_stop_moving(self) -> None:
        """Stop moving a snippet - cancelling the move operation."""
        p = self.pointer
        if p is None:
            return                                           # pragma: no cover

        w = self.find_widget(p.source)
        w.remove_class('moving')
        if isinstance(p, GroupInsertionPointer):
            for w in self.hidden_snippets:
                w.display = True
            for w in self.walk_group_widgets():
                container = cast(Horizontal, w.parent)
                top, right, _, left = container.styles.padding
                container.styles.padding = top, right, 0, left
        self.hidden_snippets.clear()
        self.pointer = None
        self.set_visuals()

    def action_toggle_order(self) -> None:
        """Toggle the order of selected snippets."""
        self.sel_order = not self.sel_order
        self.update_result()

    def action_toggle_collapse_all(self) -> None:
        """Toggle open/closed state of all groups."""
        if not self.is_fully_collapsed():
            for group in self.walk(is_group):
                self.collapsed.add(group.uid())
        else:
            self.collapsed = set()
        self.filter_view()

    def action_toggle_collapse_group(self) -> None:
        """Toggle open/closed state of selected group.

        This is triggerd by a key press. The same operation can be triggered by
        a mouse click, but is handled, differently, by `on_left_click`.
        """
        sel = self._selection_stack[-1]
        if sel.uid.startswith('snippet-'):
            group = cast(
                Snippet, self.root.find_group_child(sel.uid)).parent
            using_snippet = True
        elif sel.uid.startswith('group-'):
            group = cast(Group, self.root.find_group_child(sel.uid))
            using_snippet = False
        else:
            return                                           # pragma: no cover

        if group.uid() in self.collapsed:
            self.collapsed.remove(group.uid())
        else:
            self.collapsed.add(group.uid())
            if using_snippet:
                self._selection_stack.append(
                    Selection(uid=group.uid(), user=False))
                self.set_visuals()
        self.filter_view()

    def action_toggle_add(self):
        """Handle any key that is used to add/remove a snippet."""
        element = self.root.find_group_child(self.selection_uid)
        if isinstance(element, Snippet):
            self.push_undo()
            id_str = self.selection_uid
            if id_str in self.added:
                self.added.remove(id_str)
            else:
                self.added.append(id_str)
            self.update_selected()
            self.update_result()

    def action_toggle_tag(self, tag) -> None:
        """Toggle open/closed state of groups with a given tag."""
        tagged_groups = (
            g for g in self.walk(predicate=is_group) if tag in g.tags)
        fully_open = self.is_fully_open(tag)
        for group in tagged_groups:
            if fully_open:
                self.collapsed.add(group.uid())
            else:
                self.collapsed.discard(group.uid())
        self.filter_view()

    def action_zap_filter(self) -> None:
        """Clear he contents of the filter input field."""
        w = cast(Input, self.query_one('#filter'))
        self.on_input_changed(Input.Changed(input=w, value=''))
        w.value = ''


class Clippets(AppMixin, App):
    """The textual application object."""

    # pylint: disable=too-many-instance-attributes
    AUTO_FOCUS = None
    CSS_PATH = 'clippets.css'
    SCREENS: ClassVar[dict] = {'help': HelpScreen()}
    TITLE = 'Comment snippet wrangler'
    id_to_focus: ClassVar[dict] = {'input': 'filter'}

    def __init__(self, args):
        p = Path(args.snippet_file)
        if p.exists():
            self.loader = Loader(args.snippet_file)
        else:
            self.loader = DefaultLoader(
                DEFAULT_CONTENTS, args.snippet_file)
        root, title, err = self.loader.load()
        if err:
            raise StartupError(err)

        if title:
            self.TITLE = title                   # pylint: disable=invalid-name
        super().__init__(cast(Root, root))
        self.args = args
        self.key_handler = KeyHandler(self)
        self.init_bindings()
        self.resolver: asyncio.Task | None = None

    @property
    def no_file_yet(self):
        """True if we do not yet have a snippets file."""
        return isinstance(self.loader, snippets.DefaultLoader)

    def run(self, *args, **kwargs):                          # pragma: no cover
        """Wrap the standar run method, settin the terminal title."""
        with terminal_title('Snippet-wrangler'):
            return super().run()

    def handle_file_changed(self):
        """Handle when the current loaded file has changed."""
        def on_close(v):
            self.screen.set_focus(None)
            if  v == 'load':
                self.loader.load()
                self.rebuild()
                self.fix_selection()

        self.push_screen(FileChangedMenu(id='file-changed-menu'), on_close)

    def context_name(self) -> str:
        """Provide a name identifying the current context."""
        if self.screen.id == 'main':
            if self.pointer is not None:
                return 'moving'
            elif self.selection_uid == 'filter':
                return 'filter'
            else:
                return 'normal'
        else:
            return self.screen.id or ''

    def init_bindings(self):
        """Set up the application bindings."""
        #
        # Normal mode key bindings.
        #
        bind = partial(self.key_handler.bind, contexts=('normal',), show=False)
        bind('f8', 'toggle_order', description='Toggle order')
        bind('up', 'select_move(-1)')
        bind('down', 'select_move(1)')
        bind('left', 'select_move(-1, "horizontally")')
        bind('right', 'select_move(1, "horizontally")')
        bind('ctrl+b', 'zap_filter', description='Clear filter input')
        bind(
            'ctrl+f tab shit-tab', 'enter_filter',
            description='Enter filter input')
        bind('ctrl+u', 'do_undo', description='Undo', priority=True)
        bind('ctrl+r', 'do_redo', description='Redo', priority=True)
        bind('a', 'add_snippet')
        bind('A', 'add_group')
        bind('d', 'duplicate_snippet')
        bind('e', 'edit_snippet')
        bind('f insert', 'toggle_collapse_group')
        bind('m', 'start_moving_element', description='Move group/snippet')
        bind('r', 'rename_group')
        bind('f7', 'edit_keywords', description='Edit keywords')

        bind = partial(self.key_handler.bind, contexts=('normal',), show=True)
        bind('f1', 'show_help', description='Help')
        bind('f2', 'edit_clipboard', description='Edit')
        bind('f3', 'clear_selection', description='Clear')
        bind('f9', 'toggle_collapse_all', description='(Un)fold')
        bind('enter space', 'toggle_add', description='Toggle select')
        bind('ctrl+q', 'quit', description='Quit', priority=True)

        bind = partial(self.key_handler.bind, contexts=('moving',), show=True)
        bind(
            'up', 'move_insertion_point("up")', description='Cursor up')
        bind(
            'down', 'move_insertion_point("down")', description='Cursor down')
        bind('enter', 'complete_move', description='Insert')
        bind('escape', 'stop_moving', description='Cancel')

        # Key bindings when the filter intput field is focused.
        bind = partial(self.key_handler.bind, contexts=('filter',), show=True)
        bind(
            'ctrl+f up down tab shift-tab', 'leave_filter',
            description='Leave filter input')

        bind = partial(
            self.key_handler.bind, contexts=('editor',), show=True,
            priority=True)
        bind('ctrl+s', 'edit_save_and_quit', description='Save and quit')
        bind('ctrl+q', 'edit_quit', description='Quit and discard changes')

        bind = partial(self.key_handler.bind, contexts=('help',), show=True)
        bind('f1', 'pop_screen', description='Close help')

    async def on_exit_app(self, event):
        """Clean up when exiting the application."""
        await self.loader.stop_monitoring()
        if self.resolver:
            self.resolver_q.put_nowait(None)
            await self.resolver
        await super().on_exit_app(event)

    def compose(self) -> ComposeResult:
        """Build the widget hierarchy."""
        yield Static()
        self.add_mode('main', MainScreen(self.root, uid='main'))
        self.switch_mode('main')

    def on_setup_default_file(self):
        """Allow user to set up with default file contents."""
        async def on_close(v):
            self.screen.set_focus(None)
            if  v == 'create':
                def_loader = cast(DefaultLoader, self.loader)
                self.loader = await def_loader.become_manifest()
                self.rebuild()
                self.fix_selection()
            elif  v == 'quit':
                self.exit()

        self.push_screen(DefaulFileMenu(
            self.args.snippet_file, id='default-file-menu'), on_close)

    def active_shown_bindings(self):
        """Provide a list of bindings used for the application Footer."""
        return self.key_handler.active_shown_bindings()

    async def check_bindings(
            self, key: str,
            priority: bool = False) -> bool:             # noqa:  FBT001,FBT002
        """Handle a key press."""
        handled = False
        if priority:
            handled = await self.key_handler.handle_key(key)
        return handled or await super().check_bindings(key, priority)

    def on_ready(self) -> None:
        """React to the DOM having been created."""
        self.start_population()
        self.screen.set_focus(None)
        self.set_visuals()
        self.loader.start_monitoring(self.handle_file_changed)
        if self.no_file_yet:
            self.post_message(SetupDefaultFile())

    def action_show_help(self) -> None:
        """Show the help screen."""
        self.push_screen(HelpScreen(id='help'))

    def on_mount(self) -> None:
        """Perform app start-up actions."""
        self.dark = True
        self.start_population()

    def start_population(self):
        """Start the process of populating the snippet widgets."""
        main_screen = cast(MainScreen, self.MODES['main'])
        if self.args.sync_mode:
            populate_fg(
                partial(self.walk, predicate=is_snippet),
                main_screen.lookup_widget)
        else:
            if not self.resolver:
                self.resolver = asyncio.create_task(resolve(
                    self.resolver_q, self.lookup,
                    partial(self.walk, predicate=is_group_child),
                    self.query_one))
                self.populater = asyncio.create_task(populate(
                    self.populater_q,
                    partial(self.walk, predicate=is_snippet),
                    main_screen.lookup_widget))
            self.resolver_q.put_nowait('rebuild')
            self.populater_q.put_nowait('pop')

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
        app = self
        app._disable_tooltips = not tooltips                     # noqa: SLF001
        app_ready_event = asyncio.Event()

        def on_app_ready() -> None:
            """Note when app is ready to process events."""
            app_ready_event.set()

        async def run_app(app) -> None:
            """Run the application."""
            if message_hook is not None:
                message_hook_context_var.set(message_hook)
            app._loop = asyncio.get_running_loop()               # noqa: SLF001
            app._thread_id = threading.get_ident()               # noqa: SLF001
            await app._process_messages(                         # noqa: SLF001
                ready_callback=on_app_ready,
                headless=headless,
                terminal_size=size,
            )

        # Launch the app in the "background"
        active_message_pump.set(app)
        app_task = asyncio.create_task(run_app(app), name=f'run_test {app}')

        # Wait until the app has performed all startup routines.
        await app_ready_event.wait()

        # Get the app in an active state.
        app._set_active()                                        # noqa: SLF001

        # Context manager returns pilot object to manipulate the app
        try:
            with terminal_title('Snippet-wrangler'):
                pilot = Pilot(app)
                await pilot._wait_for_screen()                   # noqa: SLF001
                yield pilot
        finally:
            # Shutdown the app cleanly
            await app._shutdown()                                # noqa: SLF001
            await app_task
            # Re-raise the exception which caused panic so test frameworks are
            # aware
            if self._exception:
                raise self._exception                        # pragma: no cover


class KeyHandler:
    """Context specific key handling for an App."""

    def __init__(self, app: Clippets):
        self.app = app
        self.bindings: dict[tuple[str, str], Binding] = {}

    async def handle_key(self, key: str) -> bool:
        """Handle a top level key press."""
        app = self.app
        context = app.context_name()
        binding = self.bindings.get((context, key))
        if binding is not None:
            await app.run_action(binding.action)
            return True
        else:
            return False

    def bind(                                                   # noqa: PLR0913
        self,
        keys: str,
        action: str,
        *,
        contexts: Iterable[str],
        description: str = '',
        show: bool = True,
        key_display: str | None = None,
        priority: bool = False,
    ) -> None:
        """Bind a key to an action.

        Args:
            keys: A comma separated list of keys, i.e.
            action: Action to bind to.
            description: Short description of action.
            show: Show key in UI.
            key_display: Replacement text for key, or None to use default.
        """
        for key in keys.split():
            binding = Binding(
                key, action, description, show, key_display, priority)
            for context in contexts:
                self.bindings[(context, key)] = binding

    def active_shown_bindings(self):
        """Provide a list of bindings used for the application Footer."""
        context = self.app.context_name()
        return [
            binding for (ctx, key), binding in self.bindings.items()
            if ctx == context and binding.show]


async def run_editor(text: str, path: Path) -> asyncio.subprocess.Process:
    r"""Run the user's preferred editor on a textual element.

    The user's chosen editor is found using the CLIPPETS_EDITOR environment
    variable. If that is not set then a simple, internal editor (future
    feature) is used.

    At its simplest the CLIPPETS_EDITOR just provides the name/path of the
    editor program, for example::

        C:\Windows\System32\notepad.exe

    It may also include command line options, for example to use the GUI
    version of Vim you need to add the '-f' flag, to prevent it running
    itself in the background.

        /usr/bin/gvim -f

    The strings '{w}, '{h}, '{x}' and '{y}' have a special meaning. They
    will be replaced by the editor's desired size (in characterss) and
    window position (in pixels). For example

        /usr/bin/gvim -f -geom {w}x{h}+{x}+{y}

    The command is invoked with the name of a temporary file as its single
    additional argument.
    """
    edit_cmd = get_editor_command('CLIPPETS_EDITOR')
    uses_pos = '{x}' in edit_cmd and '{y}' in edit_cmd
    path.write_text(text, encoding='utf8')
    if uses_pos:                                         # pragma: no cover
        x, y = get_winpos()
        dims = {'w': 80, 'h': 25, 'x': x, 'y': y}
    else:
        dims = {'w': 80, 'h': 25}
    edit_cmd += ' ' + str(path)
    cmd = edit_cmd.format(**dims).split()
    return await asyncio.create_subprocess_exec(
        *cmd, stderr=subprocess.DEVNULL)


def parse_args(sys_args: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--raw', action='store_true',
        help='Parse clippets as raw text.')
    parser.add_argument(
        '--dump', action='store_true',
        help='On windows, dump the clipboard and quit.')
    parser.add_argument('snippet_file')

    # This is used by testing. It prevents some actions running as backgroud
    # asyncio tasks. These tasks exist to make the application appear more
    # responsive to the user, but can make it harder (or slower) to create
    # reliable snapshot based tests.
    parser.add_argument(
        '--sync-mode', action='store_true', help=argparse.SUPPRESS)
    return parser.parse_args(sys_args or sys.argv[1:])


def is_display_node(obj: GroupChild) -> type[GroupChild] | None:
    """Test if object is a Snippet."""
    display_node_types = Snippet, Group, PlaceHolder
    return GroupChild if isinstance(obj, display_node_types) else None


def main():                                                  # pragma: no cover
    """Run the application."""
    args = parse_args()
    if args.dump:
        dump_clipboard()
        sys.exit(0)
    try:
        app = Clippets(args)
    except StartupError as exc:
        sys.exit(str(exc))
    app.run()


def reset_for_tests():
    """Perform a 'system' reset for test purposes.

    This is not intended for non-testing use.
    """
    MainScreen.tag_id_sources = {}
