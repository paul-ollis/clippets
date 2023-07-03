#!/usr/bin/env python
"""Program to allow efficient composition of text snippets."""

# 2. A help page is needed.
# 3. A user guide will be needed if this is to be made available to others.
# 4. Make snippet movement:
#    - Work between groups.
#    - Support constraining the insertion point to within the group.
# 5. The keywords support needs a bigger, cleaner palette and the ability
#    to edit a group's keywords.
# 6. Global keywords?
# 7. Support full keyboard operation.
# 8. Make it work on Macs.
# 10. Genertae frozen versions for all platforms.
# 11. Watch the input file(s) and be able to 're-start' in response to changes.
# 12. Move indentation (snippet-level-2, etc) out of CSS and set in the code.

from __future__ import annotations

import argparse
import collections
import re
import shutil
import subprocess
import sys
from contextlib import suppress
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Dict, Iterable, Optional, TYPE_CHECKING, Tuple

from rich.text import Text
from textual.app import App, Binding, ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen
from textual.walk import walk_breadth_first, walk_depth_first
from textual.widgets import Header, Input, MarkdownViewer, Static

from . import snippets
from .platform import (
    SharedTempFile, get_editor_command, get_winpos, put_to_clipboard,
    terminal_title)
from .snippets import id_of_element as id_of
from .widgets import (
    MyFooter, MyInput, MyLabel, MyMarkdown, MyTag, MyText, MyVerticalScroll,
    SnippetMenu)

if TYPE_CHECKING:
    from textual.widget import Widget
    from textual.events import Event

hl_group = ''

LEFT_MOUSE_BUTTON = 1
RIGHT_MOUSE_BUTTON = 3


@dataclass
class MoveInfo:
    """Details of snippet being moved.

    @uid:      The ID of snippet being moved.
    @dest_uid: The ID of the insertion point snippet.
    """                                                            # noqa: D204
    uid: str
    dest_uid: str


def backup_file(path):
    """Create a new backup of path.

    Up to 10 numbered backups are maintained.
    """
    path = Path(path)
    dirpath = path.parent
    name = path.name
    names = [f'{name}.bak{n}' for n in range(1, 11)]
    old_names = reversed(names[:-1])
    new_names = reversed(names[1:])
    for old_name, new_name in zip(old_names, new_names):
        p = dirpath / old_name
        if p.exists():
            with suppress(OSError):
                shutil.move(p, dirpath / new_name)
    with suppress(OSError):
        shutil.copy(path, dirpath / names[0])


class Matcher:
    """Simple plain-text replacement for a compiled regular expression."""

    def __init__(self, pat: str):
        self.pat = pat.casefold()

    def search(self, text: str) -> bool:
        """Search for plain text."""
        return not self.pat or self.pat in text.lower()


banner = r'''
  ____        _                  _
 / ___| _ __ (_)_ __  _ __   ___| |_ ___
 \___ \| '_ \| | '_ \| '_ \ / _ \ __/ __|
  ___) | | | | | |_) | |_) |  __/ |_\__ \
 |____/|_| |_|_| .__/| .__/ \___|\__|___/
               |_|   |_|
'''


class HelpScreen(ModalScreen):
    """Tada."""

    def compose(self) -> ComposeResult:
        """Tada."""
        yield Header()
        yield Static(banner, classes='banner')
        help_file = Path(__file__).parent / 'help.md'
        with help_file.open() as f:
            text = f.read()
        self.md = MarkdownViewer(text, show_table_of_contents=True)
        yield self.md
        for w in walk_depth_first(self.md):
            w.add_class('help')
        yield MyFooter()

    def on_idle(self) -> None:
        """React to the DOM having been created."""
        md = self.md
        if md is not None:
            self.md = None
            s = []
            for w in walk_depth_first(md):
                s.append(f'W {type(w).__name__}: {w.id}')
            print('\n'.join(s))


class Snippets(App):
    """The textual application object."""

    TITLE = 'Comment snippet wrangler'
    CSS_PATH = 'snippets.css'
    SCREENS = {'help': HelpScreen()}
    id_to_focus = {'input': 'filter'}

    class RefreshRequired(Message):
        """Indication that the UI content needs refreshing."""

    def __init__(self, args):
        self.groups, title = snippets.load(args.snippet_file)
        if title:
            self.TITLE = title
        super().__init__()

        self.args = args
        self.chosen = []
        self.collapsed = set()
        self.filter = Matcher('')
        self.hidden_bindings = set()
        self.edited_text = ''
        self.undo_buffer = collections.deque(maxlen=20)
        self.redo_buffer = collections.deque(maxlen=20)
        self.sel_order = False
        self.hovered = collections.deque(maxlen=5)
        self.move_info = None
        self.dirty_uids = set()
        self.full_refresh_required = False
        self.hover_uid = None
        self.kb_focussed_uid = id_of(self.groups.first_snippet())
        self.key_handler = KeyHandler(self)
        self.init_bindings()

    def xrun(self, *args, **kwargs) -> int:
        """Wrap the standar run method."""
        saved = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = Path.open(
            '/tmp/snippets.log', 'wt', buffering=1)  # noqa: S108
        try:
            ret = super().run(*args, **kwargs)
            return ret
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
        bind('up', 'select_prev')
        bind('down', 'select_next')
        bind('e', 'edit_snippet')
        bind('d c', 'duplicate_snippet')
        bind('ctrl+u', 'do_undo', description='Undo', priority=True)
        bind('ctrl+r', 'do_redo', description='Redo', priority=True)
        bind('f8', 'toggle_order', description='Toggle order')
        bind('f9', 'toggle_outline', description='Toggle outline')

        bind = partial(self.key_handler.bind, ('normal',), show=True)
        bind('f1', 'show_help', description='Help')
        bind('f2', 'edit_clipboard', description='Edit')
        bind('f3', 'clear_selection', description='Clear')
        bind('f7', 'edit_keywords', description='Edit keywords')
        bind('ctrl+q', 'quit', description='Quit', priority=True)
        bind('enter space', 'toggle_select', description='Toggle select')

        bind = partial(self.key_handler.bind, ('moving',), show=True)
        bind('up', 'move_insert_up', description='Ins point up')
        bind('down', 'move_insert_down', description='Ins point down')
        bind('enter', 'complete_move', description='Insert')
        bind('escape', 'stop_moving', description='Cancel')

        bind = partial(self.key_handler.bind, ('help',), show=True)
        bind('f1', 'pop_screem', description='Close help')

    def active_shown_bindings(self):
        """Provide a list of bindings used for the application Footer."""
        return self.key_handler.active_shown_bindings()

    def on_idle(self):
        """Perform idle processing."""
        w = self._query_one(MyFooter)
        w.check_context()

    def update_hover(self, w) -> None:
        """Update the UI to indicate where the mouse is."""
        self.hover_uid = w.id
        self.set_visuals()

    def compose(self) -> ComposeResult:
        """Build the widget hierarchy."""
        yield Header()

        with Horizontal(id='input', classes='input oneline'):
            yield MyLabel('Filter: ')
            yield MyInput(placeholder='Enter text to filter.', id='filter')

        with MyVerticalScroll(id='view', classes='result'):
            yield MyMarkdown(id='result')

        all_tags = {
            t: i for i, t in enumerate( sorted(snippets.Group.all_tags))}
        with MyVerticalScroll(id='snippet-list', classes='bbb'):
            for el in self.groups.walk():
                uid = el.uid()
                if isinstance(el, snippets.Group):
                    classes = f'is_group group-level-{el.depth()}'
                    with Horizontal(classes='group_row'):
                        yield MyLabel(
                            f'-{hl_group}{el.name}', id=uid, classes=classes)
                        for tag in el.tags:
                            cls = f'tag_{all_tags[tag]}'
                            yield MyTag(
                                f'{tag}', name=tag, classes=f'tag {cls}')
                else:
                    snippet = self.make_snippet_widget(uid, el)
                    if snippet:
                        yield snippet
        footer = MyFooter()
        footer.add_class('footer')
        yield footer

    def on_ready(self) -> None:
        """React to the DOM having been created."""
        self.set_visuals()

    def make_snippet_widget(self, uid, snippet) -> Optional[Widget]:
        """Construct correct widegt for a given snnippet."""
        classes = f'is_snippet snippet-level-{snippet.depth()}'
        if isinstance(snippet, snippets.MarkdownSnippet):
            return MyMarkdown(id=uid, classes=classes)
        elif isinstance(snippet, snippets.Snippet):
            classes = f'{classes} is_text'
            return MyText(id=uid, classes=classes)
        else:
            return None

    def update_selected(self) -> None:
        """Update the 'selected' flag following mouse movement."""
        for snippet in self.groups.walk_snippets():
            id_str = snippet.uid()
            w = self.query_one(f'#{id_str}')
            if id_str in self.chosen:
                w.add_class('selected')
            else:
                w.remove_class('selected')

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
                        self.start_move_snippet(snippet.uid())
            elif not ev.meta:
                self.on_left_click(ev)
        elif ev.button == RIGHT_MOUSE_BUTTON and not ev.meta:
            self.on_right_click(ev)

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

    def fix_selection(self):
        """Update the keyboard selected focus when widgets get hidden."""
        w = self._query_one(f'#{self.kb_focussed_uid}')
        if not w.display:
            k = self.key_select_move(inc=-1, dry_run=True)
            if k == 0:
                k = self.key_select_move(inc=1, dry_run=False)
            else:
                self.key_select_move(inc=-1, dry_run=False)

    def action_select_next(self) -> None:
        """Move the keyboard driven focus to the next widget."""
        self.key_select_move(inc=1, dry_run=False)
        self.update_focus()

    def action_select_prev(self) -> None:
        """Move the keyboard driven focus to the next widget."""
        self.key_select_move(inc=-1, dry_run=False)
        self.update_focus()

    def action_edit_snippet(self) -> None:
        """Edit the currently selected snippet."""
        self.edit_snippet(self.kb_focussed_uid)

    def action_duplicate_snippet(self) -> None:
        """Duplicate and edit the currently selected snippet."""
        self.duplicate_snippet(self.kb_focussed_uid)

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

    def action_toggle_order(self) -> None:
        """Toggle the order of selected snippets."""
        self.sel_order = not self.sel_order
        self.update_result()

    def action_toggle_tag(self, tag) -> None:
        """Toggle open/closed state of groups with a given tag."""
        for group in self.groups.walk_groups(lambda g: tag in g.tags):
            if group.children and group.uid() not in self.collapsed:
                currently_open = True
                break
        else:
            currently_open = False

        for group in self.groups.walk_groups(lambda g: tag in g.tags):
            id_str = group.uid()
            if currently_open and group.children:
                self.collapsed.add(id_str)
            else:
                self.collapsed.discard(id_str)
        self.filter_view()

    def action_toggle_outline(self) -> None:
        """Toggle open/closed state of all groups."""
        for group in self.groups.walk_groups(lambda g: g.children):
            if group.uid() not in self.collapsed:
                currently_open = True
                break
        else:
            currently_open = False

        if currently_open:
            for group in self.groups.walk_groups():
                id_str = group.uid()
                if group.children:
                    self.collapsed.add(id_str)
                else:
                    self.collapsed.discard(id_str)
        else:
            self.collapsed = set()
        self.filter_view()
        self.action_clear_selection()

    def _build_result_text(self) -> None:
        if self.edited_text:
            return self.edited_text

        s = []
        if self.sel_order:
            for id_str in self.chosen:
                snippet = self.groups.find_element_by_uid(id_str)
                s.extend(snippet.md_lines())
                s.append('')
        else:
            for snippet in self.groups.walk_snippets():
                id_str = snippet.uid()
                if id_str in self.chosen:
                    s.extend(snippet.md_lines())
                    s.append('')
        if s:
            s.pop()
        return '\n'.join(s)

    def update_result(self) -> None:
        """Update the contents of the results display widget."""
        text = self._build_result_text()
        w = self.query_one('#result')
        w.update(text)
        put_to_clipboard(
            text, mode='raw' if self.args.raw else 'styled')

    def action_show_help(self) -> None:
        """Show the help screen."""
        #@ for key, (w, binding) in self.namespace_bindings.items():
        #@     if binding.show:
        #@         self.hidden_bindings.add(key)
        #@         binding.show = False
        self.push_screen(HelpScreen(id='help'))

    def push_undo(self) -> None:
        """Save state onto the undo stack."""
        if self.edited_text:
            self.undo_buffer.append(([], self.edited_text))
        else:
            self.undo_buffer.append((list(self.chosen), ''))
        self.edited_text = ''

    def action_do_undo(self) -> None:
        """Undo the last change."""
        if self.undo_buffer:
            self.redo_buffer.append((self.chosen, self.edited_text))
            self.chosen, self.edited_text = self.undo_buffer.pop()
            self.update_result()
            self.update_selected()

    def action_do_redo(self) -> None:
        """Redor the last undo action."""
        if self.redo_buffer:
            self.undo_buffer.append((self.chosen, self.edited_text))
            self.chosen, self.edited_text = self.redo_buffer.pop()
            self.update_result()
            self.update_selected()

    def action_clear_selection(self) -> None:
        """Clear all snippets from the selection."""
        self.chosen[:] = []
        self.update_result()
        self.update_selected()

    def start_move_snippet(self, id_str) -> None:
        """Start moving a snippet to a different position in the tree."""
        self.action_clear_selection()
        w = self.query_one(f'#{id_str}')
        w.add_class('moving')
        self.move_info = MoveInfo(id_str, id_str)
        self.set_visuals()

    def action_stop_moving(self) -> None:
        """Stop moving a snippet - cancelling the move operation."""
        self.move_info = None
        self.set_visuals()

    def complete_move(self) -> None:
        """Complete a snippet move operation."""
        info = self.move_info
        if not info or info.dest_uid == info.uid:
            return

        snippet = self.groups.find_element_by_uid(info.uid)
        new_lines = snippet.source_lines
        a, b = info.uid, info.dest_uid
        if self.groups.correctly_ordered(a, b):
            seq = reversed(list(self.groups.iter_from_to(a, b)))
        else:
            seq = list(self.groups.iter_from_to(b, a))

        changed = []
        backup_file(self.args.snippet_file)
        for el in seq:
            temp = list(el.source_lines)
            self.modify_snippet(el, new_lines)
            new_lines = temp
            changed.append(el.uid())

        self.schedule_refresh(*changed)

    def move_insertion_point(self, find_near_snippet) -> None:
        """Move the snippet insertion point."""
        info = self.move_info
        if info:
            new_uid = id_of(find_near_snippet(info.dest_uid))
            if new_uid is not None:
                info.dest_uid = new_uid
                self.set_visuals()

    def action_move_insert_up(self):
        """Move the snippet insetion point up."""
        self.move_insertion_point(self.groups.find_snippet_before_id)

    def action_move_insert_down(self):
        """Move the snippet insetion point up."""
        self.move_insertion_point(self.groups.find_snippet_after_id)

    def action_complete_move(self):
        """Complete a snippet move operation."""
        self.complete_move()
        self.action_stop_moving()

    async def on_key(self, ev: Event) -> None:
        """Handle a top level key press."""
        await self.key_handler.handle_key(ev)

    def schedule_refresh(self, *uids, full: bool = False):
        """Schedule the UI to refresh as soon as possible."""
        self.dirty_uids.update(uids)
        if full:
            self.full_refresh_required = True
        self.post_message(self.RefreshRequired())

    def duplicate_snippet(self, id_str: str):
        """Duplicate and the edit the current snippet."""
        snippet = self.groups.find_element_by_uid(id_str)
        if snippet is not None:
            w = self.query_one(f'#{id_str}')
            text = self.run_editor(snippet)

            curr_snippets = snippet.parent.children
            new_snippet = snippet.duplicate()
            new_snippet.set_text(text)

            i = curr_snippets.index(snippet)
            curr_snippets[i:i] = [new_snippet]

            backup_file(self.args.snippet_file)
            snippets.save(self.args.snippet_file, self.groups)

            new_widget = self.make_snippet_widget(
                new_snippet.uid(), new_snippet)
            self.mount(new_widget, after=w)
            self.schedule_refresh(new_snippet.uid())

    def on_snippets_refresh_required(self, _m) -> None:
        """Perform a requested UI refresh."""
        self.refresh_populate()

    def modify_snippet(self, snippet, lines) -> None:
        """Modify the contents of a snippet."""
        snippet.source_lines = lines
        snippets.save(self.args.snippet_file, self.groups)

    def edit_snippet(self, id_str) -> None:
        """Invoke the user's editor on a snippet."""
        snippet = self.groups.find_element_by_uid(id_str)
        if snippet is not None:
            text = self.run_editor(snippet)
            if text.strip() != snippet.text.strip():
                snippet.set_text(text)
                backup_file(self.args.snippet_file)
                snippets.save(self.args.snippet_file, self.groups)
                self.update_result()
                self.schedule_refresh(snippet.uid())

    def action_edit_keywords(self) -> None:
        """Invoke the user's editor on the current group's keyword list."""
        snippet = self.groups.find_element_by_uid(self.highlighted_snippet)
        if snippet is None:
            return

        kw = snippet.parent.keyword_set()
        text = self.run_editor(kw)
        new_words = set(text.split())
        if new_words != kw.words:
            kw.words = new_words
            backup_file(self.args.snippet_file)
            snippets.save(self.args.snippet_file, self.groups)
            for snippet in self.groups.walk_snippets():
                snippet.reset()
            self.schedule_refresh(full=True)

    def run_editor(self, text_element) -> None:
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
        text = ''
        edit_cmd = get_editor_command('SNIPPETS_EDITOR')
        with SharedTempFile() as path:
            path.write_text(text_element.text)
            x, y = get_winpos()
            dims = {'w': 80, 'h': 25, 'x': x, 'y': y}
            edit_cmd += ' ' + str(path)
            cmd = edit_cmd.format(**dims).split()
            subprocess.run(cmd, stderr=subprocess.DEVNULL)
            text = path.read_text()
        return text

    def action_edit_clipboard(self) -> None:
        """Run the user's editor on the current clipboard contents."""
        text = self._build_result_text()
        self.push_undo()
        with SharedTempFile() as path:
            x, y = get_winpos()
            orig_text = text
            path.write_text(text)
            geom = f'80x25+{x}+{y + 300}'
            subprocess.run(
                ['gvim', '-f', '-geom', geom, str(path)],          # noqa: S607
                stderr=subprocess.DEVNULL)
            text = path.read_text()
        if text.strip() != orig_text.strip():
            self.edited_text = text
            self.update_result()

    def action_close_help(self) -> None:
        """Close the help screen."""
        self.pop_screen()
        #@ for key, (w, binding) in self.namespace_bindings.items():
        #@     if key in self.hidden_bindings:
        #@         binding.show = True
        #@ self.hidden_bindings = set()

    def on_mount(self) -> None:
        """Perform app start-up actions."""
        #@ self.query_one(Input).focus()
        self.dark = True
        self.populate()

    def populate(self) -> None:
        """Populate the UI  snippet tree content."""
        for snippet in self.groups.walk_snippets():
            w = self.query_one(f'#{snippet.uid()}')
            w.update(snippet.marked_text)

    def refresh_populate(self) -> None:
        """Refressh changed content of the UI snippet tree."""
        for snippet in self.groups.walk_snippets():
            uid = snippet.uid()
            if uid in self.dirty_uids or self.full_refresh_required:
                w = self.query_one(f'#{snippet.uid()}')
                w.update(snippet.marked_text)
        self.dirty_uids = set()

    def filter_view(self) -> None:
        """Hide snippets that have been filtered out of folded away."""
        def st_opened():
            return all(ste.uid() not in self.collapsed for ste in stack)

        matcher = self.filter
        stack = []
        opened = True
        for el in self.groups.walk():
            if isinstance(el, snippets.Group):
                while stack and stack[-1].depth() >= el.depth():
                    stack.pop()
                w = self.query_one(f'#{el.uid()}')
                if st_opened():
                    w.display = True
                    w.parent.display= True
                else:
                    w.display = False
                    w.parent.display = False

                opened = el.uid() not in self.collapsed
                if opened:
                    w.update(Text.from_markup(f'-{hl_group}{el.name}'))
                else:
                    w.update(Text.from_markup(f'+{hl_group}{el.name}'))

                stack.append(el)
                opened = st_opened()

            else:
                try:
                    w = self.query_one(f'#{el.uid()}')
                except NoMatches:
                    pass
                else:
                    w.display = bool(matcher.search(el.text)) and opened
        self.fix_selection()

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

    def _query_one(self, selector) -> Optional[Widget]:
        """Search for a single widget without raising NoMatches."""
        try:
            return self.query_one(selector)
        except NoMatches:
            return None

    def focussable_widgets(self) -> Tuple[Widget, ...]:
        """Create a tuple of 'focussable' widgets."""
        a = [self._query_one('#input')]
        b = (
            self._query_one(f'#{s.uid()}')
            for s in self.groups.walk_snippets())
        return (*a, *b)

    def set_visuals(self) -> None:
        """Set and clear widget classes that control visual highlighting."""
        for w in self.focussable_widgets():
            w.remove_class('kb_focussed')
            w.remove_class('mouse_hover')
            w.remove_class('moving')
            w.remove_class('dest_above')
            w.remove_class('dest_below')
            if self.move_info is not None:
                info = self.move_info
                if w.id == info.uid:
                    w.add_class('moving')
                elif w.id == info.dest_uid and info.dest_uid != info.uid:
                    if self.groups.correctly_ordered(info.uid, info.dest_uid):
                        w.add_class('dest_below')
                    else:
                        w.add_class('dest_above')
            else:
                if w.id == self.kb_focussed_uid:
                    w.add_class('kb_focussed')
                if w.id == self.hover_uid:
                    w.add_class('mouse_hover')

    def update_focus(self):
        """Set input focus according to the keyboard selected widget."""
        if self.move_info is None and self.kb_focussed_uid == 'input':
            self.screen.set_focus(self._query_one('#filter'))
        else:
            self.screen.set_focus(None)


class ContextualBinding:
    """A key binding associated with one or more contexts."""

    def __init__(self, binding: Binding, contexts: Iterable[str]):
        self.binding = binding
        self.contexts = set(contexts)


class KeyHandler:
    """Context specific key handling for an App."""

    def __init__(self, app):
        self.app = app
        self.bindings: Dict[Tuple(str, str), Binding] = {}

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


def parse_args() -> argparse.Namespace:
    """Run the snippets application."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--raw', action='store_true',
        help='Parse snippets as raw text.')
    parser.add_argument('snippet_file')
    return parser.parse_args()


def main():
    """Run the application."""
    app = Snippets(parse_args())
    with terminal_title('Snippet-wrangler'):
        app.run()
