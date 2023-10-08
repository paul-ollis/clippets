"""Program to allow efficient composition of text snippets."""
# pylint: disable=too-many-lines

# 6. Global keywords?
# 8. Make it work on Macs.
# 10. Generate frozen versions for all platforms.

from __future__ import annotations

import argparse
import asyncio
import itertools
import os
import re
import subprocess
import sys
import time
import traceback
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from functools import partial, wraps
from pathlib import Path
from typing import Callable, ClassVar, Iterator, TYPE_CHECKING, Union, cast

from rich.syntax import Syntax
from rich.text import Text
from textual.app import App, Binding, ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import Screen
from textual.walk import walk_depth_first
from textual.widgets import Header, Input, Static
from textual.widgets._markdown import MarkdownFence

from . import markup, robot, snippets
from .debug import DebugBase, DebugPanel, DummyDebugPanel
from .editor import TextArea
from .platform import (
    SharedTempFile, dump_clipboard, get_editor_command, get_winpos,
    put_to_clipboard, terminal_title)
from .snippets import (
    CannotMove, DefaultLoader, Group, GroupChild, GroupInsertionPointer,
    GroupPlaceHolder, Loader, MarkdownSnippet, PlaceHolder, Root, Snippet,
    SnippetInsertionPointer, SnippetLike, is_group, is_group_child, is_snippet,
    is_snippet_like)
from .widgets import (
    DefaulFileMenu, FileChangedMenu, GreyoutScreen, GroupMenu, GroupNameMenu,
    MyFooter, MyInput, MyLabel, MyMarkdown, MyTag, MyText, MyVerticalScroll,
    SnippetMenu)

from . import patches

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from textual.binding import _Bindings
    from textual.timer import Timer
    from textual.widget import Widget

HL_GROUP = ''
LEFT_MOUSE_BUTTON = 1
RIGHT_MOUSE_BUTTON = 3
BANNER = r'''
 ____    ___                                __
/\  _`\ /\_ \    __                        /\ \__
\ \ \/\_\//\ \  /\_\  _____   _____      __\ \ ,_\   ____
 \ \ \/_/_\ \ \ \/\ \/\ '__`\/\ '__`\  /'__`\ \ \/  /',__\
  \ \ \L\ \\_\ \_\ \ \ \ \L\ \ \ \L\ \/\  __/\ \ \_/\__, `\
   \ \____//\____\\ \_\ \ ,__/\ \ ,__/\ \____\\ \__\/\____/
    \/___/ \/____/ \/_/\ \ \/  \ \ \/  \/____/ \/__/\/___/
                        \ \_\   \ \_\
                         \/_/    \/_/
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
    """Information about a general selection.

    @uid:    The ID of the slected widget.
    @user: True if the user manually made the selection.
    """

    uid: str
    user: bool

    def __repr__(self):
        mode = 'user' if self.user else 'auto'
        return f'Sel-{mode}:{self.uid}'


@dataclass
class TreeSelection(Selection):
    """Information about a selection within the snippet tree.

    @uid:    The ID of the slected widget.
    @user: True if the user manually made the selection.
    """

    element: Snippet| Group

    def __repr__(self):
        mode = 'user' if self.user else 'auto'
        return f'TreeSel-{mode}:{self.uid}'


class Selector:
    """The tracker of the current selection.

    This class enforces the following invariants.

    1. if active_group then active_snippet None or a child of active_group.

    @snippet_sel:
        A `TreeSelection` for the most recently selected snippet. This may be
        ``None``, in which case `group_sel` will not be ``None``.
    @group_sel:
        A `TreeSelection` for the most recently selected group. This may be
        ``None``, in which case `snippet` will not be ``None``.
    @search:
        A `Selection` for the search snippet. This is only set if the user is
        currently searching.
    """

    snippet_sel: TreeSelection | None
    group_sel: TreeSelection | None
    search_sel: Selection | None

    def __init__(self, *, snippet: Snippet | None, group: Group | None):
        self.on_set_callback:Callable[[GroupChild], None] = self.null_cb
        self.init(snippet=snippet, group=group, user=False)

    # TODO: Questionable name.
    def init(
            self, *,
            snippet: Snippet | None = None,
            group: Group | None = None,
            user: bool):
        """Re-initialise with just a group or snipper."""
        self.snippet_sel = self.group_sel = self.search_sel = None
        if snippet:
            self.set_snippet(snippet, user=user)
        else:
            self.set_group(group, user=user)

    @property
    def searching(self) -> bool:
        """True if the search box is currently selected."""
        return self.search_sel is not None

    @property
    def snippet(self) -> Snippet | None:
        """The selected snippet, active or not."""
        return self.snippet_sel and cast(Snippet, self.snippet_sel.element)

    @property
    def group(self) -> Group | None:
        """The selected group, active or not."""
        return self.group_sel and cast(Group, self.group_sel.element)

    @property
    def active_group(self) -> Group | None:
        """The active selected group or None."""
        if self.search_sel:
            return None                                      # pragma: no cover
        else:
            sel = self.group_sel
            return cast(Group, sel.element) if sel else None

    @property
    def active_snippet(self) -> Snippet | None:
        """The active selected snippet or None."""
        if self.search_sel or self.group_sel:
            return None
        else:
            sel = self.snippet_sel
            return cast(Snippet, sel.element) if sel else None

    @property
    def active_element(self) -> GroupChild | None:
        """The active selected snippet or group."""
        if self.search_sel:
            return None                                      # pragma: no cover
        elif self.group_sel:
            return self.group_sel.element
        else:
            return self.snippet_sel.element

    @property
    def active_sel(self) -> Selection:
        """The active selection."""
        if self.search_sel:
            return self.search_sel
        elif self.group_sel:
            return self.group_sel
        else:
            return self.snippet_sel

    @property
    def current_tree_sel(self) -> Selection | None:
        """The currently active tree selection, if any"""
        if self.search_sel:
            return None
        else:
            return self.active_sel

    def set_snippet(self, snippet: Snippet, *, user: bool) -> None:
        """Set the selected snippet."""
        if self.snippet is not snippet or self.group is not None:
            self.snippet_sel = TreeSelection(snippet.uid(), user, snippet)
            assert isinstance(self.snippet_sel, TreeSelection)
            self.group_sel = None
            self.on_set_callback(snippet)

    def set_group(self, group: Group, *, user: bool) -> None:
        """Set the selected snippet."""
        if self.group is not group:
            self.group_sel = TreeSelection(group.uid(), user, group)
            if self.snippet and self.snippet.parent is not group:
                self.snippet_sel = None
            self.on_set_callback(group)

    def handle_group_fold(self, group: Group):
        """Move selection to a newly folded group if necessary."""
        if self.active_snippet and self.active_snippet.parent is group:
            self.set_group(group, user=False)

    def set_search(self, *, user: bool) -> None:
        """Set the search box as the current selection."""
        self.search_sel = Selection('filter', user)

    def unset_search(self) -> None:
        """Unset the search box as the current selection."""
        self.search_sel = None

    def restore_snippet(self, check: Callable[[Snippet], bool]) -> bool:
        """Attempt to restore selection to last selected snippet.

        :check:
            A function that is used to check if any previous snippet is
            currently usable as a selection.
        :return:
            True if restoration occurred.
        """
        if self.group_sel and check(self.snippet):
            self.group_sel = None
            return True
        else:
            return False

    def null_cb(self, el: GroupChild) -> None:
        """Provide dummy on_set_callback."""

    def __repr__(self):
        s = []
        if self.search_sel:
            s.append(f'{self.search_sel.uid}')
        if self.group_sel:
            s.append(f'{self.group_sel.uid}')
        if self.snippet_sel:
            s.append(f'{self.snippet_sel.uid}')
        return ' -> '.join(s)


class SetupDefaultFile(Message):
    """An inidication that we need to create a default file."""


class EditorHasExited(Message):
    """An indication the extenal editor has exited."""


class ScreenGreyedOut(Message):
    """An indication the screen has been greyed out."""


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
            if isinstance(cc.renderable, Syntax):            # pragma: no cover
                cc.renderable.padding = 0, 0, 0, 0
                cc.renderable.indent_guides = False


class MainScreen(Screen):
    """Main Clippets screen."""

    tag_id_sources: ClassVar[dict[str, itertools.count]] = {}
    app: Clippets
    debug: DebugBase

    def __init__(self, root: Root, uid: str):
        super().__init__(name='main', id=uid)
        self.root = root
        self.walk = root.walk
        self.widgets: dict[str, Widget] = {}

    def compose(self) -> ComposeResult:
        """Build the widget hierarchy."""
        yield Header(id='header')
        with Horizontal(id='input', classes='input oneline') as h:
            yield MyLabel('Filter: ')
            inp = MyInput(placeholder='Enter text to filter.', id='filter')
            inp.cursor_blink = False
            inp.can_focus = False
            yield inp
        h.can_focus = False
        h.can_focus_children = False
        with MyVerticalScroll(id='view', classes='result') as view:
            view_height = self.app.args.view_height
            if view_height:
                view.styles.height = view_height             # pragma: no cover
            if self.app.args.raw:
                yield Static(id='result')
            else:
                yield MyMarkdown(id='result')
        with MyVerticalScroll(id='snippet-list', classes='bbb'):
            yield from self.build_tree_part()
        if self.app.args.debug:                              # pragma: no cover
            self.debug = DebugPanel(id='debug')
            yield self.debug
        else:
            self.debug = DummyDebugPanel()
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
            if isinstance(el, (Group, GroupPlaceHolder)):
                w = self.make_group_widget(uid, el, all_tags)
                self.widgets[uid] = w
                yield w
            elif isinstance(el, (Snippet, PlaceHolder)):
                w = make_snippet_widget(uid, el)
                self.widgets[uid] = w
                yield w

    def make_group_widget(
            self, uid: str, group: Group | GroupPlaceHolder,
            all_tags: dict[str, int],
        ) -> Widget:
        """Construct correct widget for a given group or place holder."""
        classes = 'is_group'
        fields = []
        if isinstance(group, GroupPlaceHolder):
            classes += ' is_placehoder'
            label = MyLabel(
                f'{HL_GROUP}{group.name}', id=uid, classes=classes)
        else:
            label = MyLabel(
                f'▽ {HL_GROUP}{group.name}', id=uid, classes=classes)
            for tag in group.tags:
                classes = f'tag_{all_tags[tag]}'
                fields.append(MyTag(
                    f'{tag}', id=self.gen_tag_id(tag), name=tag,
                    classes=f'tag {classes}'))
        w = Horizontal(label, *fields, classes='group_row')
        w.styles.margin = 0, 0, 0, (group.depth() - 1) * 4
        return w

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


def make_snippet_widget(uid: str, snippet: Snippet | PlaceHolder) -> Widget:
    """Construct correct widget for a given snippet or placeholder."""
    classes = 'is_snippet'
    w: MyMarkdown | MyText | Static | None = None
    if isinstance(snippet, MarkdownSnippet):
        w = MyMarkdown(id=uid, classes=classes)
    elif isinstance(snippet, Snippet):
        classes = f'{classes} is_text'
        w = MyText(id=uid, classes=classes)
    else:
        classes = f'{classes} is_placehoder'
        w = Static('-- place holder --', id=uid, classes=classes)
        w.display = False
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
            on_complete: Callable[[str, bool], None]):
        self.app = app
        self.on_complete = on_complete

    def save(self):
        """Save the changes from the editor."""
        ta = self.app.query_one('TextArea')
        text = '\n'.join(ta.lines)
        self.app.pop_screen()
        self.app.edit_session = None
        self.on_complete(text, False)

    def quit(self):                                                # noqa: A003
        """Quite the editor."""
        self.app.pop_screen()
        self.app.edit_session = None
        self.on_complete('', True)


class ExtEditSession(EditSession):
    """Encapsulation of an external editing session."""

    def __init__(
            self,
            app: Clippets,
            temp_path: SharedTempFile,
            proc: asyncio.subprocess.Process |None,
            on_complete: Callable[[str, bool], None]):
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
            self.on_complete(text, not bool(text.strip()))
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
    post_message: Callable
    selector: Selector
    _bindings: _Bindings
    MODES: ClassVar[dict[str, str | Screen | Callable[[], Screen]]]

    def __init__(self, root: Root):
        super().__init__()
        for name in list(self.MODES):
            if name != '_default':
                self.MODES.pop(name)
        self.added: list[str] = []
        self.collapsed: set[str] = set()
        self.filtered: set[str] = set()
        self.edited_text = ''
        self.root = root
        self.hover_uid = None
        self.selector = Selector(
            snippet=self.root.first_snippet(), group=self.root.first_group())
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
        return self.selector.active_sel.uid

    @property
    def selection(self) -> tuple[GroupChild, Widget] | tuple[None, None]:
        """The currently selected element and widget."""
        sel = self.selector.current_tree_sel
        if sel:
            el = self.root.find_group_child(sel.uid)
            if el:
                return el, self.find_widget(el)
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

    def find_widget(self, el: SnippetLike | str) -> Widget:
        """Find the widget for a given element or ID string."""
        if isinstance(el, str):
            return self.find_widget_by_uid(el)
        else:
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
        """Set and clear widget classes that control visual highlighting.

        This needs to be called whenever the selection stack is changed.
        """
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
            if isinstance(dest.child, (Group, GroupPlaceHolder)):
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
        p = self.pointer
        moving_group = p and isinstance(p.source, Group)
        for el in self.walk(predicate=is_display_node):
            w = self.find_widget(el)
            w.remove_class('kb_focussed')
            w.remove_class('mouse_hover')
            self._clear_move_marker(el, w)
            if isinstance(el, PlaceHolder):
                w.display = False
            if p is not None:
                if moving_group and isinstance(el, GroupPlaceHolder):
                    w.display = True
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
    async def on_my_input_clicked(self, msg: Message):
        """React to a click on the filter input widget."""
        w = getattr(msg, 'widget', None)
        if w is not None and w.id == 'filter':
            self.action_enter_search()

    async def on_click(self, ev) -> None:                          # noqa: C901
        """Process a mouse click."""
        # Prevent default Textual handling doing things like changing the
        # focus.
        context = self.context_name()
        if context == 'normal':
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

        elif context == 'filter' and ev.button == LEFT_MOUSE_BUTTON:
            self.on_left_click(ev)

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
        # If the filter input is focused, just switch back to normal mode.
        if self.context_name() == 'filter':
            self.action_leave_search()
            return

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
            self._toggle_group_fold(el)
            self.set_visibilty()

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
            # Note: Menu screen is popped before this is called.
            self.screen.set_focus(None)
            if  v == 'add_snippet':
                await self.add_snippet(wid)
            elif  v == 'add_group':
                await self.add_group(wid)
            elif  v == 'rename_group':
                await self.rename_group(wid)

        wid = cast(str, w.id)
        group = self.root.find_group_child(wid)
        if group:
            self.push_screen(GroupMenu(id='group-menu'), on_close)

    async def on_right_click_snippet(self, w: Widget) -> None:
        """Process a mouse right-click on a snippet."""

        async def on_close(v):
            # Note: Menu screen is popped before this is called.
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
    # TODO: Put this in a sensible place.
    def _scroll_visible(self, element: GroupChild):
        """Scroll so that the givent group or snippet is visible."""
        try:
            w = self.find_widget(element.uid())
        except NoMatches:
            return
        w.scroll_visible(animate=False)

    def action_select_move(
            self, inc: int, mode: str ='vertically', *, user: bool = True,
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
        selector = self.selector
        if mode == 'vertically':
            return self.select_move_vertically(inc, user=user)
        else:
            return self.select_move_horizontally(inc, user=user)

    def select_move_vertically(self, inc: int, *, user: bool) -> bool:
        """Move the selection to the next available snippet.

        :inc:  -1 => move up, 1 => move down.
        :push: If set then push the new selection onto the selection stack.
               Otherwise replace the stack with the new selection.
        :user: If set then the user is making the move. Otherwise this move was
               triggered by an automatic adjustment.
        :return:
            True if a widget was succesffuly selected.
        """
        if self.selector.active_group:
            return self.move_vertically_group_wise(inc, user=user)
        else:
            return self.move_vertically_snippet_wise(inc, user=user)

    def move_vertically_snippet_wise(self, inc: int, *, user: bool) -> bool:
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
        snippet = cast(Snippet, self.selector.active_snippet)
        for next_snippet in self.root.walk(
                predicate=is_snippet, after=snippet, backwards=inc < 0):
            next_widget = self.find_widget(next_snippet)
            if next_widget.display:
                self.selector.set_snippet(next_snippet, user=user)
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
        group = cast(Group, self.selector.active_group)
        next_group = group.step_group(backwards=inc < 0)
        while next_group is not None:
            next_widget = self.find_widget(next_group)
            if next_widget.display:
                w = self.find_widget(next_group)
                self.selector.set_group(next_group, user=user)
                self.set_visuals()
                w.scroll_visible(animate=False)
                return
            else:
                next_group = next_group.step_group(backwards=inc < 0)

    def select_move_horizontally(self, inc: int, *, user: bool):
        """Move the selection to/from group mode."""
        selector = self.selector
        if inc == -1 and not selector.active_group:
            # Moving into group mode.
            group = selector.active_snippet.parent
            selector.set_group(group, user=user)
            w = self.find_widget(group)
            self.set_visuals()
            w.scroll_visible(animate=False)

        elif inc == 1 and selector.active_group:
            # See if we can restore the previous snippet selection.
            if not selector.restore_snippet(self._snippet_is_visible):
                # We cannot restore a previous selection, chosse a visible
                # snippet from the group.
                for snippet in selector.active_group.snippets():
                    if self.find_widget(snippet).display:
                        selector.set_snippet(snippet, user=user)
                        self.find_widget(snippet.uid()).scroll_visible(
                            animate=False)
                        break
            self.set_visuals()

    ## Ways to limit visible snippets.
    def set_visibilty(self) -> None:
        """Set the visibility of snippets, base on folds and search filter."""
        def st_folded():
            """Test if current group or anu ancestors is folded."""
            return any(ste.uid() in self.collapsed for ste in group_stack)

        def set_disp_if_changed(w: Widget, *, flag: bool):
            """Set display flag if it has changed."""
            if w.display != flag:
                w.display = flag

        # TODO: Make used of _iter_snippet_visibilty
        group_stack: list[GroupChild] = []
        folded = False
        for el in self.walk(predicate=is_group_child):
            if isinstance(el, Group) and not isinstance(el, PlaceHolder):
                # Remove exited layers of the group stack.
                while group_stack and group_stack[-1].depth() >= el.depth():
                    group_stack.pop()

                # Set the visibility of this group's widgets.
                w = cast(MyLabel, self.find_widget(el))
                w_parent = cast(MyLabel, w.parent)
                visible = not st_folded()
                set_disp_if_changed(w, flag=visible)
                set_disp_if_changed(w_parent, flag=visible)

                # Set the group lable to indicate the folded state.
                folded = el.uid() in self.collapsed
                if folded:
                    w.update(Text.from_markup(f'▶ {HL_GROUP}{el.name}'))
                else:
                    w.update(Text.from_markup(f'▽ {HL_GROUP}{el.name}'))

                # Add the group to the stack and set the folded indicator for
                # use with snippet processing in later iterations.
                group_stack.append(el)
                folded = st_folded()

            elif isinstance(el, Snippet) and not isinstance(el, PlaceHolder):
                w = self.find_widget(el)
                hidden = folded or w.id in self.filtered
                set_disp_if_changed(w, flag=not hidden)

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
        if not self.selector.searching:
            return

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
            for snippet in self.walk(predicate=is_snippet):
                if rexp.search(snippet.text):
                    self.filtered.discard(snippet.uid())
                else:
                    self.filtered.add(snippet.uid())
            self.set_visibilty()

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
        try:
            put_to_clipboard(
                text, mode='raw' if self.args.raw else 'styled')
        except (OSError, subprocess.CalledProcessError):     # pragma: no cover
            if not self.args.svg_run:
                raise

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
                self.selector.set_group(new_group, user=True)
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

        def on_edit_complete(text: str, aborted: bool):
            if not aborted:
                new_snippet = add()
                new_snippet.set_text(text)
                self.selector.set_snippet(new_snippet, user=True)
                self.rebuild_after_edits()
                w = self.find_widget(new_snippet)
                w.scroll_visible(animate=False)
                self.set_visuals()

        if id_str.startswith('snippet-'):
            snippet = cast(Snippet, self.root.find_group_child(id_str))
            add = partial(snippet.add_new)
        elif id_str.startswith('group-'):
            group = cast(Group, self.root.find_group_child(id_str))
            add = partial(group.add_new)
        await self.run_editor(
            '', 'Currently editing a new snippet', on_edit_complete)

    def backup_and_save(self):
        """Create a new snippet file backup and then save."""
        snippets.backup_file(self.args.snippet_file)
        self.loader.save(self.root)                # type: ignore[attr-defined]

    async def duplicate_snippet(self, id_str: str):
        """Duplicate and the edit the current snippet."""

        def on_edit_complete(text, aborted: bool):
            if not aborted:
                new_snippet = add()
                new_snippet.set_text(text)
                self.selector.set_snippet(new_snippet, user=True)
                self.rebuild_after_edits()
                w = self.find_widget(new_snippet)
                w.scroll_visible(animate=False)
                self.set_visuals()

        if id_str.startswith('snippet-'):
            snippet = cast(Snippet, self.root.find_group_child(id_str))
            text = snippet.text
            add = partial(snippet.duplicate)
            await self.run_editor(
                text, 'Currently editing a duplicate snippet',
                on_edit_complete)

    async def edit_snippet(self, id_str) -> None:
        """Invoke the editor on a snippet."""

        def on_edit_complete(text, aborted: bool):
            if not aborted and text.strip() != snippet.text.strip():
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
        self.set_visibilty()
        self.set_visuals()

    def rebuild_after_edits(self):
        """Rebuild, refresh, *etc*. after changes to the snippets tree."""
        self.backup_and_save()
        self.rebuild()

    async def run_editor(
            self, text: str, message: str,
            on_complete: Callable[[str, bool], None]) -> None:
        """Run the user's preferred editor on a textual element."""
        ext_editor = get_editor_command('CLIPPETS_EDITOR', '')
        if ext_editor:
            self.push_screen(GreyoutScreen(message, id='greyout'))
            self.post_message(ScreenGreyedOut())
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

    ## Snippet and group position movement.
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
        def is_usable(el: SnippetLike) -> bool:
            w = self.find_widget(el)
            return w.display or isinstance(el, PlaceHolder) if w else False

        try:
            self.pointer = SnippetInsertionPointer(snippet, is_usable)
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
                self.selector.set_snippet(p.source, user=True)
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
        def on_edit_complete(new_text: str, aborted: bool):
            if new_text.strip() != text.strip():
                self.edited_text = new_text
                self.update_result()

        text = self.build_result_text()
        self.push_undo()
        await self.run_editor(
            text, 'Currently editing clipboard contents', on_edit_complete)

    async def action_edit_keywords(self) -> None:
        """Invoke the user's editor on the current group's keyword list."""
        def on_edit_complete(new_text: str, aborted: bool):
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

    def action_enter_search(self) -> None:
        """Move focus to the filter input field."""
        w = self.query_one('#filter')
        w.can_focus = True
        self.screen.set_focus(w)
        self.selector.set_search(user=True)
        self.set_visuals()

    def action_leave_search(self) -> None:
        """Move focus away from the filter input field.

        The previous active snippet selection is restored if possible.
        """
        selector = self.selector
        if selector.searching:
            w = self.query_one('#filter')
            w.can_focus = False
            selector.unset_search()
            self._reestablish_selector()
        self._scroll_visible(selector.active_element)
        self.screen.set_focus(None)
        self.set_visuals()

    # TODO: Put in sensible place.
    def _reestablish_selector(self):
        """Re-establish most approrpaiet selector, if possible."""
        selector = self.selector
        if not selector.active_group:
            snippet = selector.snippet
            if not self._snippet_is_visible(snippet):
                fallback_snippet = self._find_selectable_snippet()
                if not fallback_snippet:
                    selector.set_group(snippet.parent, user=False)
                else:
                    selector.init(
                        snippet=fallback_snippet,
                        group=self.root.first_group(),
                        user=False)

    # TODO: Put in sensible place.
    def _find_selectable_snippet(self) -> Snippet | None:
        """Find the first selectable snippet."""
        for snippet, visible in self._iter_snippet_visibilty():
            if visible:
                return snippet
        return None

    def _iter_snippet_visibilty(self) -> Iterator[tuple[Snippet, bool]]:
        """Iterate over all snippet, testing visibility.

        :yield: A tuple of the snippet and ``True`` if the snippet is visible.
        """
        for el in self.walk(predicate=is_group_child):
            if isinstance(el, PlaceHolder):
                continue
            if isinstance(el, Group):
                folded = self._group_is_folded(el)
            elif isinstance(el, Snippet):
                hidden = folded or el.uid() in self.filtered
                yield el, not hidden

    def _group_is_folded(self, group: Group) -> bool:
        """Test whether a group or one if its ancestors is folded."""
        return group.uid() in self.collapsed or any(
            g.uid() in self.collapsed for g in group.ancestors)

    def _snippet_is_visible(self, snippet: Snippet) -> bool:
        """Test whether a given snippet is visible."""
        if not snippet:
            return False
        elif snippet.uid() in self.filtered:
            return False
        else:
            return not self._group_is_folded(snippet.parent)

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

    def _fold_group(self, group: Group):
        """Fold a given group.

        :group: The group to be folded.
        """
        if group.uid() not in self.collapsed:
            self.collapsed.add(group.uid())
            self.selector.handle_group_fold(group)
            self.set_visuals()
            self.set_visibilty()

    def _unfold_group(self, group: Group):
        """Unfoldold a given group.

        :group: The group to be unfolded.
        """
        if group.uid() in self.collapsed:
            self.collapsed.remove(group.uid())
            self.set_visibilty()
            if self.selector.restore_snippet(self._snippet_is_visible):
                self.set_visuals()

    def _toggle_group_fold(self, group: Group):
        """Toggle the folded state of a group."""
        if group.uid() in self.collapsed:
            self._unfold_group(group)
        else:
            self._fold_group(group)

    def action_toggle_collapse_all(self) -> None:
        """Toggle open/closed state of all groups."""
        if not self.is_fully_collapsed():
            for group in self.walk(is_group):
                self._fold_group(group)
        else:
            for group in self.walk(is_group):
                self._unfold_group(group)
            self._scroll_visible(self.selector.active_element)
        self.set_visibilty()

    def action_toggle_collapse_group(self) -> None:
        """Toggle open/closed state of selected group.

        This is triggerd by a key press. The same operation can be triggered by
        a mouse click, but is handled, differently, by `on_left_click`.
        """
        selector = self.selector
        if selector.active_group:
            self._toggle_group_fold(selector.active_group)
        elif selector.active_snippet:
            self._toggle_group_fold(selector.active_snippet.parent)

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
                self._fold_group(group)
            else:
                self._unfold_group(group)
        self.set_visibilty()

    def action_zap_filter(self) -> None:
        """Clear the contents of the filter input field."""
        w = cast(Input, self.query_one('#filter'))
        w.value = ''
        self.filtered.clear()
        self.set_visibilty()
        if self.selector.restore_snippet(self._snippet_is_visible):
            self.set_visuals()

class Clippets(AppMixin, App):
    """The textual application object."""

    ENABLE_COMMAND_PALETTE = False
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
                self.selector.init(
                    snippet=self.root.first_snippet(),
                    group=self.root.first_group(),
                    user=False)
                self.set_visuals()

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
        bind('up k', 'select_move(-1)')
        bind('down j', 'select_move(1)')
        bind('left h', 'select_move(-1, "horizontally")')
        bind('right l', 'select_move(1, "horizontally")')
        bind('ctrl+b', 'zap_filter', description='Clear filter input')
        bind(
            'ctrl+f tab shift-tab', 'enter_search',
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
        bind('enter space', 'toggle_add', description='Toggle add')
        bind('ctrl+q', 'quit', description='Quit', priority=True)

        bind = partial(self.key_handler.bind, contexts=('moving',), show=True)
        bind(
            'up k', 'move_insertion_point("up")', description='Cursor up')
        bind(
            'down j', 'move_insertion_point("down")',
            description='Cursor down')
        bind('enter', 'complete_move', description='Insert')
        bind('escape', 'stop_moving', description='Cancel')

        # Key bindings when the search intput field is focused.
        bind = partial(self.key_handler.bind, contexts=('filter',), show=True)
        bind(
            'ctrl+f up down tab shift-tab', 'leave_search',
            description='Leave filter input')
        bind('ctrl+q', 'quit', description='Quit', priority=True)

        # Key bindings when the intenal editor is active.
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
        s = Static(id='fred')
        s.display = False
        yield s
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
        self.selector.on_set_callback = self._scroll_visible
        if self.no_file_yet:
            self.post_message(SetupDefaultFile())
        debug = self.screen.debug
        debug.connect('Selection', self.selector, repr)

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

    def bind(                              # pylint: disable=too-many-arguments
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
    parser.add_argument('snippet_file', type=Path)

    # This is used by testing. It prevents some actions running as backgroud
    # asyncio tasks. These tasks exist to make the application appear more
    # responsive to the user, but can make it harder (or slower) to create
    # reliable snapshot based tests.
    add_hidden_arg = partial(parser.add_argument, help=argparse.SUPPRESS)
    add_hidden_arg( '--sync-mode', action='store_true')
    add_hidden_arg('--svg', type=Path)
    add_hidden_arg('--svg-run', action='store_true')
    add_hidden_arg('--work-dir', type=Path)
    add_hidden_arg('--dims', type=str)
    add_hidden_arg('--dummy-editor', action='store_true')
    add_hidden_arg('--view-height', type=int)
    add_hidden_arg('--debug', action='store_true')
    return parser.parse_args(sys_args or sys.argv[1:])


def is_display_node(obj: GroupChild) -> type[GroupChild] | None:
    """Test if object is a Snippet."""
    display_node_types = Snippet, Group, PlaceHolder
    return GroupChild if isinstance(obj, display_node_types) else None


def perform_svg_run(args: argparse.Namespace) -> None:       # pragma: no cover
    """Performa run in order to generate an SVG image."""
    def resolve_includes(lines):
        """Resolve simple-include directives."""
        include_lines = []
        for i, line in enumerate(lines):
            if line.startswith('@simple-include: '):
                p = args.snippet_file.parent / line[17:].strip()
                include_lines.append((i, p.read_text().splitlines()))
        for i, inc_lines in reversed(include_lines):
            lines[i:i + 1] = inc_lines
        return [line.rstrip() for line in lines]

    # This is for document generation. We want color regardless of the
    # user's environment. The 'Read the Docs' builder sets NO_COLOR
    # (without a by-your-leave), which is rather unhelpful. Here we
    # undefine it while setting both TERM and  FORCE_COLOR for good
    # measure.
    os.environ.pop('NO_COLOR', None)
    os.environ['TERM'] = 'xterm-256color'
    os.environ['FORCE_COLOR'] = 'yes'

    # Use the working directory if specified.
    args.svg = args.svg.resolve()
    work_dir = args.work_dir
    if work_dir:
        work_dir.mkdir(exist_ok=True)
        for p in work_dir.glob('*'):
            p.unlink()
        new_path = work_dir / args.snippet_file.name
        if args.snippet_file.exists():
            lines = args.snippet_file.read_text().splitlines()
            new_path.write_text('\n'.join(resolve_includes(lines)))
        os.chdir(work_dir)
        args.snippet_file = Path(args.snippet_file.name)

    try:
        robot.run_capture(
            args, make_app=lambda args: Clippets(parse_args(args)))
    except Exception as e:             # pylint: disable=broad-exception-caught
        traceback.print_exc()
        sys.exit(str(e))


def main():                                                  # pragma: no cover
    """Run the application."""
    args = parse_args()
    if args.dump:
        dump_clipboard()
        sys.exit(0)
    elif args.svg:
        perform_svg_run(args)
    else:
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
