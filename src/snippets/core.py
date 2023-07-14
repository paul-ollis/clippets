#!/usr/bin/env python
"""Program to allow efficient composition of text snippets."""
# pylint: disable=too-many-lines

# 2. A help page is needed.
# 3. A user guide will be needed if this is to be made available to others.
# 5. The keywords support needs a bigger, cleaner palette and the ability
#    to edit a group's keywords.
# 6. Global keywords?
# 8. Make it work on Macs.
# 10. Genertae frozen versions for all platforms.
# 11. Watch the input file(s) and be able to 're-start' in response to changes.

# 12. Fix edit - copy/reuse move code.
# 13. Fix duplicate - copy/reuse move code.
from __future__ import annotations

import argparse
import asyncio
import collections
import re
import subprocess
import sys
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial, wraps
from pathlib import Path
from typing import AsyncGenerator, Callable, ClassVar, Iterable, TYPE_CHECKING

from rich.text import Text
from textual._context import (
    active_message_pump, message_hook as message_hook_context_var)
from textual.app import App, Binding, ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.message import Message
from textual.pilot import Pilot
from textual.screen import Screen
from textual.walk import walk_depth_first
from textual.widgets import Header, Input, Static

from . import markup, snippets
from .platform import (
    SharedTempFile, get_editor_command, get_winpos, put_to_clipboard,
    terminal_title)
from .snippets import (
    Group, Snippet, SnippetInsertionPointer, SnippetLike,
    id_of_element as id_of)
from .widgets import (
    MyFooter, MyInput, MyLabel, MyMarkdown, MyTag, MyText, MyVerticalScroll,
    SnippetMenu)

if TYPE_CHECKING:
    import io

    from textual.widget import Widget
    from textual.events import Event

HL_GROUP = ''

LEFT_MOUSE_BUTTON = 1
RIGHT_MOUSE_BUTTON = 3


@dataclass
class MoveInfo:
    """Details of snippet being moved.

    @uid:      The ID of snippet being moved.
    @dest_uid: The ID of the insertion point snippet.
    """

    source: Snippet
    dest: SnippetInsertionPointer

    def unmoved(self):
        """Test if the destination is the same as the source."""
        return self.source == self.dest.snippet


def if_active(method):
    """Wrap Smippets method to only run when fully active."""
    @wraps(method)
    def invoke(self, *args, **kwargs):
        if self.active:
            return method(self, *args, **kwargs)
        else:
            return None

    return invoke


class Matcher:                         # pylint: disable=too-few-public-methods
    """Simple plain-text replacement for a compiled regular expression."""

    def __init__(self, pat: str):
        self.pat = pat.casefold()

    def search(self, text: str) -> bool:
        """Search for plain text."""
        return not self.pat or self.pat in text.lower()


BANNER = r'''
  ____        _                  _
 / ___| _ __ (_)_ __  _ __   ___| |_ ___
 \___ \| '_ \| | '_ \| '_ \ / _ \ __/ __|
  ___) | | | | | |_) | |_) |  __/ |_\__ \
 |____/|_| |_|_| .__/| .__/ \___|\__|___/
               |_|   |_|
'''


class RefreshRequired(Message):
    """Indication that the UI content needs refreshing."""


class HelpScreen(Screen):
    """Tada."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timer = None

    def compose(self) -> ComposeResult:
        """Tada."""
        yield Header()
        yield Static(BANNER, classes='banner')
        yield from markup.generate()
        yield MyFooter()

    def on_screen_resume(self):
        """Fix code block styling as soon as possible."""
        for c in walk_depth_first(self):
            if c.__class__.__name__ == 'MarkdownFence':
                for cc in walk_depth_first(c):
                    if cc.__class__.__name__ == 'Static':
                        cc.renderable.padding = 0, 0, 0, 0
                        cc.renderable.indent_guides = False
                        print('>>>', cc, cc.renderable.padding)


class MainScreen(Screen):
    """Main Snippets screen."""

    def __init__(self, groups: Group):
        super().__init__(name='main')
        self.groups = groups
        self.walk = partial(groups.walk, backwards=False)

    def compose(self) -> ComposeResult:
        """Build the widget hierarchy."""
        yield Header()

        with Horizontal(id='input', classes='input oneline'):
            yield MyLabel('Filter: ')
            yield MyInput(placeholder='Enter text to filter.', id='filter')
        with MyVerticalScroll(id='view', classes='result'):
            yield MyMarkdown(id='result')
        with MyVerticalScroll(id='snippet-list', classes='bbb'):
            yield from self.build_tree_part()
        footer = MyFooter()
        footer.add_class('footer')
        yield footer

    def build_tree_part(self):
        """Yield widgets for the tree part of the UI."""
        all_tags = {
            t: i for i, t in enumerate(sorted(Group.all_tags))}
        for el in self.walk():
            uid = el.uid()
            if isinstance(el, Group):
                classes = 'is_group'
                label = MyLabel(
                    f'▽ {HL_GROUP}{el.name}', id=uid, classes=classes)
                fields = []
                for tag in el.tags:
                    classes = f'tag_{all_tags[tag]}'
                    fields.append(
                        MyTag(f'{tag}', name=tag, classes=f'tag {classes}'))
                w = Horizontal(label, *fields, classes='group_row')
                w.styles.padding = (0, 0, 0, (el.depth() - 1) * 4)
                yield w
            else:
                snippet = make_snippet_widget(uid, el)
                if snippet:
                    yield snippet

    def rebuild_tree_part(self):
        """Rebuild the tree part of the UI."""
        top = self.query_one('#snippet-list')
        top.remove_children()
        top.mount(*self.build_tree_part())

    def on_idle(self):
        """Perform idle processing."""
        w = self.query_one(MyFooter)
        w.check_context()


def make_snippet_widget(uid, snippet) -> Widget | None:
    """Construct correct widegt for a given snnippet."""
    classes = 'is_snippet'
    w = None
    if isinstance(snippet, snippets.MarkdownSnippet):
        w = MyMarkdown(id=uid, classes=classes)
    elif isinstance(snippet, Snippet):
        classes = f'{classes} is_text'
        w = MyText(id=uid, classes=classes)
    elif isinstance(snippet, snippets.PlaceHolder):
        classes = f'{classes} is_placehoder'
        w = Static('-- place holder --', id=uid, classes=classes)

    if w:
        w.styles.margin = (0, 1, 0, (snippet.depth() - 1) * 4)
    return w


class AppMixin:
    """The main Snippets screen."""

    # pylint: disable=too-many-public-methods
    # pylint: disable=too-many-instance-attributes
    args: argparse.Namespace
    mount: Callable
    post_message: Callable
    push_screen: Callable
    _query_one: Callable
    screen: Screen

    def __init__(self, groups: Group):
        super().__init__()
        self.chosen = []
        self.collapsed = set()
        self.dirty_uids = set()
        self.edited_text = ''
        self.filter = Matcher('')
        self.full_refresh_required = False
        self.groups = groups
        self.hidden_bindings = set()
        self.hovered = collections.deque(maxlen=5)
        self.hover_uid = None
        self.kb_focussed_uid = id_of(self.groups.first_snippet())
        self.move_info = None
        self.redo_buffer = collections.deque(maxlen=20)
        self.sel_order = False
        self.undo_buffer = collections.deque(maxlen=20)
        self.walk = partial(self.groups.walk, backwards=False)

    ## Management of dynanmic display features.
    def focussable_widgets(self) -> tuple[Widget, ...]:
        """Create a tuple of 'focussable' widgets."""
        a = [self._query_one('#input')]
        b = (
            self._query_one(f'#{s.uid()}')
            for s in self.walk_snippets())
        return (*a, *b)

    def insertion_widgets(self) -> tuple[Widget, ...]:
        """Create a tuple of widgets involved in insetion operations."""
        a = [self._query_one('#input')]
        b = (
            self._query_one(f'#{s.uid()}')
            for s in self.walk_snippet_like())
        return (*a, *b)

    def on_snippets_refresh_required(self, _m) -> None:
        """Perform a requested UI refresh."""
        self.refresh_populate()

    def schedule_refresh(self, *uids, full: bool = False):
        """Schedule the UI to refresh as soon as possible."""
        self.dirty_uids.update(uids)
        if full:
            self.full_refresh_required = True
        self.post_message(RefreshRequired())

    @if_active
    def set_visuals(self) -> None:
        """Set and clear widget classes that control visual highlighting."""
        for w in self.insertion_widgets():
            w.remove_class('kb_focussed')
            w.remove_class('mouse_hover')
            w.remove_class('moving')
            w.remove_class('dest_above')
            w.remove_class('dest_below')
            if self.move_info is not None:
                info = self.move_info
                source, dest = info.source, info.dest
                if w.id == source.uid():
                    w.add_class('moving')
                else:
                    uid, after = dest.addr
                    if uid != source.uid() and uid == w.id:
                        w.add_class('dest_below' if after else 'dest_above')
            else:
                if w.id == self.kb_focussed_uid:
                    w.add_class('kb_focussed')
                if w.id == self.hover_uid:
                    w.add_class('mouse_hover')

    @if_active
    def update_selected(self) -> None:
        """Update the 'selected' flag following mouse movement."""
        for snippet in self.walk_snippets():
            id_str = snippet.uid()
            w = self._query_one(f'#{id_str}')
            if id_str in self.chosen:
                w.add_class('selected')
            else:
                w.remove_class('selected')

    ## Handling of mouse operations.
    def on_click(self, ev) -> None:
        """Process a mouse click."""
        if self.move_info:
            return

        if ev.button == LEFT_MOUSE_BUTTON:
            if ev.meta:
                w = getattr(ev, 'snippet', None)
                if w:
                    snippet = self.groups.find_element_by_uid(w.id)
                    if snippet:
                        self.action_start_moving_snippet(snippet.uid())
            elif not ev.meta:
                self.on_left_click(ev)
        elif ev.button == RIGHT_MOUSE_BUTTON and not ev.meta:
            self.on_right_click(ev)

    def on_left_click(self, ev) -> None:
        """Process a mouse left-click."""
        snippet = getattr(ev, 'snippet', None)
        if snippet:
            self.push_undo()
            id_str = snippet.id
            if id_str in self.chosen:
                self.chosen.remove(id_str)
            else:
                self.chosen.append(id_str)
            self.update_selected()
            self.update_result()

        group = getattr(ev, 'group', None)
        if group:
            id_str = group.id
            if id_str in self.collapsed:
                self.collapsed.remove(id_str)
            else:
                self.collapsed.add(id_str)
            self.filter_view()

        tag = getattr(ev, 'tag', None)
        if tag:
            self.action_toggle_tag(tag.name)

    def on_right_click(self, ev) -> None:
        """Process a mouse right-click."""
        def on_close(v):
            if  v == 'edit':
                self.edit_snippet(w.id)
            elif  v == 'duplicate':
                self.duplicate_snippet(w.id)

        w = getattr(ev, 'snippet', None)
        if w:
            self.push_screen(SnippetMenu(), on_close)

    ## Handling of keyboard operations.
    def fix_selection(self):
        """Update the keyboard selected focus when widgets get hidden."""
        w = self._query_one(f'#{self.kb_focussed_uid}')
        if not w.display:
            k = self.key_select_move(inc=-1, dry_run=True)
            if k == 0:
                k = self.key_select_move(inc=1, dry_run=False)
            else:
                self.key_select_move(inc=-1, dry_run=False)

    def key_select_move(self, inc: int, *, dry_run: bool) -> None:
        """Move the keyboard driven focus to the next available widget."""
        widgets = self.focussable_widgets()
        valid_widgets = [w for w in widgets if w.display]
        valid_range = range(len(widgets))

        k = -1
        for i, w in enumerate(widgets):
            if w.id == self.kb_focussed_uid:
                k = i + inc
                while k in valid_range and not widgets[k].display:
                    k += inc
                break

        # Note that widgets[0] is always present and visible.
        if k not in valid_range:
            k = 0 if k < 0 else len(valid_widgets) - 1
        if dry_run:
            return k

        self.kb_focussed_uid = widgets[k].id
        self.set_visuals()
        return k

    def update_focus(self):
        """Set input focus according to the keyboard selected widget."""
        if self.move_info is None and self.kb_focussed_uid == 'input':
            self.screen.set_focus(self._query_one('#filter'))
        else:
            self.screen.set_focus(None)

    ## Ways to limit visible snippets.
    def filter_view(self) -> None:
        """Hide snippets that have been filtered out or folded away."""
        def st_opened():
            return all(ste.uid() not in self.collapsed for ste in stack)

        matcher = self.filter
        stack = []
        opened = True
        for el in self.walk(backwards=False):
            if isinstance(el, Group):
                while stack and stack[-1].depth() >= el.depth():
                    stack.pop()
                w = self._query_one(f'#{el.uid()}')
                if st_opened():
                    w.display = True
                    w.parent.display= True
                else:
                    w.display = False
                    w.parent.display = False

                opened = el.uid() not in self.collapsed
                if opened:
                    w.update(Text.from_markup(f'▽ {HL_GROUP}{el.name}'))
                else:
                    w.update(Text.from_markup(f'▶ {HL_GROUP}{el.name}'))

                stack.append(el)
                opened = st_opened()

            else:
                w = self._query_one(f'#{el.uid()}')
                if w is not None:
                    w.display = bool(matcher.search(el.text)) and opened
        self.fix_selection()

    ## UNCLASSIFIED
    def populate(self) -> None:
        """Populate the UI  snippet tree content."""
        for snippet in self.walk_snippets():
            w = self._query_one(f'#{snippet.uid()}')
            w.update(snippet.marked_text)

    def refresh_populate(self) -> None:
        """Refressh changed content of the UI snippet tree."""
        for snippet in self.walk_snippets():
            uid = snippet.uid()
            if uid in self.dirty_uids or self.full_refresh_required:
                w = self._query_one(f'#{snippet.uid()}')
                w.update(snippet.marked_text)
        self.dirty_uids = set()

    async def on_input_changed(self, message: Input.Changed) -> None:
        """Handle a text changed message."""
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

    def update_hover(self, w) -> None:
        """Update the UI to indicate where the mouse is."""
        self.hover_uid = w.id
        self.set_visuals()

    def push_undo(self) -> None:
        """Save state onto the undo stack."""
        if self.edited_text:
            self.undo_buffer.append(([], self.edited_text))
        else:
            self.undo_buffer.append((list(self.chosen), ''))
        self.edited_text = ''

    ## Clipboard representaion widget management.
    @if_active
    def update_result(self) -> None:
        """Update the contents of the results display widget."""
        text = self.build_result_text()
        w = self._query_one('#result')
        w.update(text)
        put_to_clipboard(
            text, mode='raw' if self.args.raw else 'styled')

    def build_result_text(self) -> None:
        """Build up the text that should be copied to the clipboard."""
        if self.edited_text:
            return self.edited_text

        s = []
        if self.sel_order:
            for id_str in self.chosen:
                snippet = self.groups.find_element_by_uid(id_str)
                s.extend(snippet.md_lines())
                s.append('')
        else:
            for snippet in self.walk_snippets():
                id_str = snippet.uid()
                if id_str in self.chosen:
                    s.extend(snippet.md_lines())
                    s.append('')
        if s:
            s.pop()
        return '\n'.join(s)

    ## Editing and duplicating snippets.
    def edit_snippet(self, id_str) -> None:
        """Invoke the user's editor on a snippet."""
        snippet = self.groups.find_element_by_uid(id_str)
        if snippet is not None:
            text = run_editor(snippet)
            if text.strip() != snippet.text.strip():
                snippet.set_text(text)
                self.save_with_backup()
                self.update_result()
                self.schedule_refresh(snippet.uid())

    def duplicate_snippet(self, id_str: str):
        """Duplicate and the edit the current snippet."""
        snippet = self.groups.find_element_by_uid(id_str)
        if snippet is not None:
            w = self._query_one(f'#{id_str}')
            text = run_editor(snippet)
            curr_snippets = snippet.parent.children
            new_snippet = snippet.duplicate()
            new_snippet.set_text(text)

            i = curr_snippets.index(snippet)
            curr_snippets[i:i] = [new_snippet]
            self.save_with_backup()

            new_widget = make_snippet_widget(new_snippet.uid(), new_snippet)
            self.mount(new_widget, after=w)
            self.schedule_refresh(new_snippet.uid())

    def save_with_backup(self):
        """Create a new snippet file backup and then save."""
        snippets.backup_file(self.args.snippet_file)
        snippets.save(self.args.snippet_file, self.groups)

    ## Snippet position movement.
    def complete_move(self) -> None:              # pylint: disable=no-self-use
        """Complete a snippet move operation."""
        if self.move_info and not self.move_info.unmoved():
            self.move_info.dest.move_snippet(self.move_info.source)
            self.screen.rebuild_tree_part()
            self.populate()
            self.schedule_refresh(full=True)
            self.save_with_backup()

    def modify_snippet(self, snippet, lines) -> None:
        """Modify the contents of a snippet."""
        snippet.source_lines = lines
        snippets.save(self.args.snippet_file, self.groups)

    def action_start_moving_snippet(
            self, id_str: str | None = None) -> None:
        """Start moving a snippet to a different position in the tree."""
        id_str = id_str or self.kb_focussed_uid
        self.action_clear_selection()
        w = self._query_one(f'#{id_str}')
        w.add_class('moving')

        snippet = self.groups.find_element_by_uid(id_str)
        dest = SnippetInsertionPointer(snippet)
        self.move_info = MoveInfo(snippet, dest)
        self.set_visuals()

    ## Binding handlers.
    def action_clear_selection(self) -> None:
        """Clear all snippets from the selection."""
        self.chosen[:] = []
        #@ self.update_result()
        self.update_selected()

    def action_complete_move(self):
        """Complete a snippet move operation."""
        self.complete_move()
        self.action_stop_moving()

    def action_do_redo(self) -> None:
        """Redor the last undo action."""
        if self.redo_buffer:
            self.undo_buffer.append((self.chosen, self.edited_text))
            self.chosen, self.edited_text = self.redo_buffer.pop()
            self.update_result()
            self.update_selected()

    def action_do_undo(self) -> None:
        """Undo the last change."""
        if self.undo_buffer:
            self.redo_buffer.append((self.chosen, self.edited_text))
            self.chosen, self.edited_text = self.undo_buffer.pop()
            self.update_result()
            self.update_selected()

    def action_duplicate_snippet(self) -> None:
        """Duplicate and edit the currently selected snippet."""
        self.duplicate_snippet(self.kb_focussed_uid)

    def action_edit_clipboard(self) -> None:
        """Run the user's editor on the current clipboard contents."""
        text = self.build_result_text()
        self.push_undo()
        with SharedTempFile() as path:
            x, y = get_winpos()
            orig_text = text
            path.write_text(text, encoding='utf8')
            geom = f'80x25+{x}+{y + 300}'
            subprocess.run(
                ['gvim', '-f', '-geom', geom, str(path)],          # noqa: S607
                stderr=subprocess.DEVNULL, check=False)
            text = path.read_text(encoding='utf8')
        if text.strip() != orig_text.strip():
            self.edited_text = text
            self.update_result()

    def action_edit_keywords(self) -> None:
        """Invoke the user's editor on the current group's keyword list."""
        snippet = self.groups.find_element_by_uid(self.kb_focussed_uid)
        if snippet is None:
            return

        kw = snippet.parent.keyword_set()
        text = run_editor(kw)
        new_words = set(text.split())
        if new_words != kw.words:
            kw.words = new_words
            self.save_with_backup()
            for snippet in self.walk_snippets():
                snippet.reset()
            self.schedule_refresh(full=True)

    def action_edit_snippet(self) -> None:
        """Edit the currently selected snippet."""
        self.edit_snippet(self.kb_focussed_uid)

    def action_move_insertion_point(self, direction: str):
        """Move the snippet insertion up of down.

        :direction: Either 'up' or 'down'.
        """
        snippet, dest = self.move_info.source, self.move_info.dest
        if dest.move(backwards=direction == 'up', skip=snippet):
            self.set_visuals()

    def action_select_next(self) -> None:
        """Move the keyboard driven focus to the next widget."""
        self.debug('NEXT')
        self.key_select_move(inc=1, dry_run=False)
        self.update_focus()

    def action_select_prev(self) -> None:
        """Move the keyboard driven focus to the next widget."""
        self.key_select_move(inc=-1, dry_run=False)
        self.update_focus()

    def action_stop_moving(self) -> None:
        """Stop moving a snippet - cancelling the move operation."""
        self.move_info = None
        self.set_visuals()

    def action_toggle_order(self) -> None:
        """Toggle the order of selected snippets."""
        self.sel_order = not self.sel_order
        self.update_result()

    def action_toggle_outline(self) -> None:
        """Toggle open/closed state of all groups."""
        for group in self.walk(is_group):
            if group.uid() not in self.collapsed:
                currently_open = True
                break
        else:
            currently_open = False

        if currently_open:
            for group in self.walk(is_group):
                id_str = group.uid()
                if group.children:
                    self.collapsed.add(id_str)
                else:
                    self.collapsed.discard(id_str)
        else:
            self.collapsed = set()
        self.filter_view()
        self.action_clear_selection()

    def action_toggle_select(self):
        """Handle any key that is used to select a snippet."""
        if self.groups.find_element_by_uid(self.kb_focussed_uid) is not None:
            self.push_undo()
            id_str = self.kb_focussed_uid
            if id_str in self.chosen:
                self.chosen.remove(id_str)
            else:
                self.chosen.append(id_str)
            self.update_selected()
            self.update_result()

    def action_toggle_tag(self, tag) -> None:
        """Toggle open/closed state of groups with a given tag."""
        for group in self.walk(is_group):
            if tag in group.tags and group.uid() not in self.collapsed:
                currently_open = True
                break
        else:
            currently_open = False

        for group in self.walk(is_group):
            if tag in group.tags and currently_open:
                self.collapsed.add(group.uid())
            else:
                self.collapsed.discard(group.uid())
        self.filter_view()

    def debug(self, *args):
        """Log a message, purely for debug purposes."""
        if self.logf:
            print(*args, file=self.logf)


class Snippets(AppMixin, App):
    """The textual application object."""

    # pylint: disable=too-many-instance-attributes
    TITLE = 'Comment snippet wrangler'
    CSS_PATH = 'snippets.css'
    SCREENS: ClassVar[dict] = {'help': HelpScreen()}
    id_to_focus: ClassVar[dict] = {'input': 'filter'}

    def __init__(self, args, logf: io.TextIOWrapper | None = None):
        self.logf = logf
        groups, title = snippets.load(args.snippet_file)
        if title:
            self.TITLE = title                   # pylint: disable=invalid-name
        super().__init__(groups)
        self.args = args
        self.active = False
        self.key_handler = KeyHandler(self)
        self.init_bindings()
        self.walk_snippets = partial(
            self.walk, predicate=is_snippet, backwards=False)
        self.walk_snippet_like = partial(
            self.walk, predicate=is_snippet_like, backwards=False)

    def xrun(self, *args, **kwargs) -> int:
        """Wrap the standar run method."""
        # pylint: disable=unspecified-encoding
        saved = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = Path('/tmp/snippets.log').open(  # noqa: S108
            'wt', buffering=1)
        try:
            return super().run(*args, **kwargs)
        finally:
            sys.stdout, sys.stderr = saved

    def context_name(self) -> str:
        """Provide a name identifying the current context."""
        if self.screen.id == 'help':
            return 'help'
        elif self.move_info is None:
            return 'normal'
        else:
            return 'moving'

    def init_bindings(self):
        """Set up the application bindings."""
        bind = partial(self.key_handler.bind, ('normal',), show=False)
        bind('f8', 'toggle_order', description='Toggle order')
        bind('f9', 'toggle_outline', description='Toggle outline')
        bind('up', 'select_prev')
        bind('down', 'select_next')
        bind('ctrl+f', 'edit_filter', description='Edit filter', priority=True)
        bind('ctrl+u', 'do_undo', description='Undo', priority=True)
        bind('ctrl+r', 'do_redo', description='Redo', priority=True)
        bind('e', 'edit_snippet')
        bind('d c', 'duplicate_snippet')
        bind('m', 'start_moving_snippet', description='Move snippet')

        bind = partial(self.key_handler.bind, ('normal',), show=True)
        bind('f1', 'show_help', description='Help')
        bind('f2', 'edit_clipboard', description='Edit')
        bind('f3', 'clear_selection', description='Clear')
        bind('f7', 'edit_keywords', description='Edit keywords')
        bind('ctrl+q', 'quit', description='Quit', priority=True)
        bind('enter space', 'toggle_select', description='Toggle select')

        bind = partial(self.key_handler.bind, ('moving',), show=True)
        bind(
            'up', 'move_insertion_point("up")', description='Cursor up')
        bind(
            'down', 'move_insertion_point("down")', description='Cursor down')
        bind('enter', 'complete_move', description='Insert')
        bind('escape', 'stop_moving', description='Cancel')

        bind = partial(self.key_handler.bind, ('help',), show=True)
        bind('f1', 'pop_screen', description='Close help')

    def compose(self) -> ComposeResult:
        """Build the widget hierarchy."""
        yield Static()
        self.add_mode('main', MainScreen(self.groups))
        self.switch_mode('main')

    def active_shown_bindings(self):
        """Provide a list of bindings used for the application Footer."""
        return self.key_handler.active_shown_bindings()

    def on_ready(self) -> None:
        """React to the DOM having been created."""
        self.screen.set_focus(None)
        self.active = True
        self.set_visuals()

    def action_show_help(self) -> None:
        """Show the help screen."""
        self.push_screen(HelpScreen(id='help'))

    def action_close_help(self) -> None:
        """Close the help screen."""
        self.pop_screen()

    async def on_key(self, ev: Event) -> None:
        """Handle a top level key press."""
        await self.key_handler.handle_key(ev)

    def on_mount(self) -> None:
        """Perform app start-up actions."""
        #@ self._query_one(Input).focus()
        self.dark = True
        self.populate()

    def _query_one(self, selector) -> Widget | None:
        """Search for a single widget without raising NoMatches."""
        try:
            return self.query_one(selector)
        except NoMatches:
            return None

    @asynccontextmanager
    async def run_test(
        self,
        *,
        headless: bool = True,
        size: tuple[int, int] | None = (80, 24),
        tooltips: bool = False,
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
            """Yada."""
            if message_hook is not None:
                message_hook_context_var.set(message_hook)
            app._loop = asyncio.get_running_loop()               # noqa: SLF001
            # pylint: disable=undefined-variable
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
        self.debug('Wait for app_ready')
        await app_ready_event.wait()
        self.debug('Done: Wait for app_ready')

        # Get the app in an active state.
        app._set_active()                                        # noqa: SLF001

        # Context manager returns pilot object to manipulate the app
        try:
            self.debug('Create Pilot')
            pilot = Pilot(app)
            await pilot._wait_for_screen()                       # noqa: SLF001
            yield pilot
        finally:
            # Shutdown the app cleanly
            await app._shutdown()                                # noqa: SLF001
            await app_task
            # Re-raise the exception which caused panic so test frameworks are
            # aware
            if self._exception:
                raise self._exception


class KeyHandler:
    """Context specific key handling for an App."""

    def __init__(self, app):
        self.app = app
        self.bindings: dict[tuple(str, str), Binding] = {}

    async def handle_key(self, ev: Event) -> None:
        """Handle a top level key press."""
        app = self.app
        context = app.context_name()
        binding = self.bindings.get((context, ev.key))
        if binding is not None:
            await app.run_action(binding.action)

    def bind(                                                   # noqa: PLR0913
        self,
        contexts: Iterable[str],
        keys: str,
        action: str,
        *,
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


def run_editor(text_element) -> None:
    r"""Run the user's preferred editor on a textual element.

    The user's chosen editor is found using the SNIPPETS_EDITOR environment
    variable. If that is not set then a simple, internal editor (future
    feature) is used.

    At its simplest the SNIPPETS_EDITOR just provides the name/path of the
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
    """
    edit_cmd = get_editor_command('SNIPPETS_EDITOR')
    with SharedTempFile() as path:
        path.write_text(text_element.text, encoding='utf8')
        x, y = get_winpos()
        dims = {'w': 80, 'h': 25, 'x': x, 'y': y}
        edit_cmd += ' ' + str(path)
        cmd = edit_cmd.format(**dims).split()
        subprocess.run(cmd, stderr=subprocess.DEVNULL, check=False)
        return path.read_text(encoding='utf8')


def parse_args() -> argparse.Namespace:
    """Run the snippets application."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--raw', action='store_true',
        help='Parse snippets as raw text.')
    parser.add_argument('snippet_file')
    return parser.parse_args()


def is_type(obj, *, classinfo):
    """Test is one of a set of types.

    This simply wraps the built-in isinstance, but plays nucely with
    functools.partial.
    """
    return isinstance(obj, classinfo)


# Useful parital functions for Group.walk.
is_snippet = partial(is_type, classinfo=Snippet)
is_snippet_like = partial(is_type, classinfo=SnippetLike)
is_group = partial(is_type, classinfo=Group)


def main():
    """Run the application."""
    app = Snippets(parse_args())
    with terminal_title('Snippet-wrangler'):
        app.run()
