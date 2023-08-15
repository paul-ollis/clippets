"""Simple test editor.

This is a modified version of Ted Conbeer's textual-textarea widget.

    https://github.com/tconbeer/textual-textarea

A lot of the code in here is Ted's. Most of my changes are refactorings or
removal of features that to not fit with Clippets' somewhat more minimal
requirements. The changes include:

- Removed anything to do with saving and loading files.
- Editor text is now set using a list of lines.
- Code commenting related code removed.
- The TextArea is a subclass of VerticalScroll.

I also plan:

- To add a simple help page.
- Perhaps a toggle for markdown/plain text.
"""
from __future__ import annotations

import re
from typing import Callable, NamedTuple, TYPE_CHECKING, cast, Literal

from rich.color import Color as RichColor
from rich.style import Style
from rich.syntax import PygmentsSyntaxTheme, Syntax
from textual.color import Color
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static
from textual.containers import ScrollableContainer

if TYPE_CHECKING:
    from rich.console import RenderableType
    from textual import events
    from textual.app import ComposeResult
    from textual.events import MouseEvent

r_word_boundary = re.compile(r'\W*\w+\b')

ArrowName = Literal['left', 'right', 'up', 'down']


class WidgetColors(NamedTuple):
    """Colours extracted or derived from a colour scheme."""

    bgcolor: Color
    selection_bgcolor: Color


class TextAreaCursorMoved(Message, bubble=True):
    """Posted when the cursor moves.

    :cursor_x: The x position of the cursor
    :cursor_y: The y position (line number)
    """

    def __init__(self, cursor_x: int, cursor_y: int) -> None:
        super().__init__()
        self.cursor_x = cursor_x
        self.cursor_y = cursor_y


class Cursor(NamedTuple):
    """Representation of the cursor position."""

    lidx: int
    cidx: int

    @classmethod
    def from_mouse_event(cls, event: MouseEvent) -> Cursor:
        """Create a Cursor from a mouse event."""
        return Cursor(event.y, event.x - 1)

    def inc(self, linc, cinc):
        """Create cursor moved by a number of columns."""
        return Cursor(self.lidx + linc, self.cidx + cinc)

    def inc_column(self, inc):
        """Create cursor moved by a number of columns."""
        return Cursor(self.lidx, self.cidx + inc)

    def inc_line(self, inc):
        """Create cursor moved by a number of columns."""
        return Cursor(self.lidx + inc, self.cidx)


class TextInput(Static, can_focus=True):
    """The widget that handles the editor's text.

    This is a specialisation of the textual.Static widget.
    """

    DEFAULT_CSS = '''
        TextInput {
            height: auto;
            width: auto;
            padding: 0 0;
        }
    '''
    lines: reactive[list[str]] = reactive(lambda: list(' '))
    cursor: reactive[Cursor] = reactive(Cursor(0, 0))
    selection_anchor: reactive[Cursor | None] = reactive(None)
    cursor_visible: reactive[bool] = reactive(default=True)
    parent: ScrollableContainer

    def __init__(
            self,
            theme_colors: WidgetColors,
            on_changed: Callable[[list[str]], None],
            theme: str = 'github-dark',
            **kwargs,
        ) -> None:
        super().__init__(**kwargs)
        self.theme_colors = theme_colors
        self.theme = theme
        self.clipboard: list[str] = []
        self.on_changed = on_changed

    def update(self, renderable: RenderableType = '') -> None:
        """Update this widget's contents and invoke on_change callback."""
        super().update(renderable)
        self.on_changed(self.lines)

    def on_focus(self) -> None:
        """Handle Focus event."""
        self.cursor_visible = True
        self._scroll_to_cursor()
        self.update(self.content)

    def on_blur(self) -> None:                               # pragma: no cover
        """Handle Blur event."""
        self.cursor_visible = False
        self.update(self.content)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Move the anchor and cursor to the click."""
        event.stop()
        self.selection_anchor = Cursor.from_mouse_event(event)
        self.move_cursor(event.x - 1, event.y)
        self.focus()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Move the cursor if button 1 is pressed."""
        if event.button == 1:
            self.move_cursor(event.x - 1, event.y)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Move the cursor to the click."""
        event.stop()
        if self.selection_anchor == Cursor.from_mouse_event(event):
            # simple click
            self.selection_anchor = None
        else:
            self.move_cursor(event.x - 1, event.y)
        self.focus()

    @staticmethod
    def on_click(event: events.Click) -> None:
        """Kill the event.

        Click duplicates MouseUp and MouseDown, so we just capture and kill
        this event.
        """
        event.stop()

    def on_key(self, event: events.Key) -> None:
        """Handle a keypress."""
        with_sel_handlers = (
            self._handle_cut_and_paste_keys,
            self._handle_deletion_keys,
        )
        without_sel_handlers = (
            self._handle_movement_key,
            self._handle_tab_key,
            self._handle_enter_key,
        )
        modifier, sep, name = event.key.rpartition('+')
        modifiers = set() if sep != '+' else set(modifier.split('+'))
        char = cast(str, event.character)

        event_handled = False
        for handler in with_sel_handlers:
            if handler(name, char, modifiers):
                event_handled = True
                break
        else:
            if event.is_printable:
                self._insert_char(char)
                event_handled = True
            else:
                self.adjust_selection_for_key(name, modifiers)
                for handler in without_sel_handlers:
                    if handler(name, char, modifiers):
                        event_handled = True
                        break

        if event_handled:
            event.stop()
        self.update(self.content)

    def _insert_char(self, character: str):
        """Insert a character at the cursor."""
        selection_before = self.selection_anchor
        if selection_before is not None:
            self._delete_selection(selection_before, self.cursor)
            self.selection_anchor = None
        self._insert_character_at_cursor(character, self.cursor)
        self.cursor = self.cursor.inc_column(len(character))

    def adjust_selection_for_key(self, key: str, modifiers: set[str]):
        """Adjust the selection anchor in response to a key press."""
        selection_before = self.selection_anchor
        special_control_keys = set('cx')
        if 'shift' in modifiers:
            if not selection_before:
                self.selection_anchor = self.cursor
        elif 'ctrl' not in modifiers and key not in special_control_keys:
            self.selection_anchor = None

    def _handle_movement_key(self, name: str, char: str, modifiers: set[str]):
        """Handle special movement keys, page up, *etc*."""
        lidx, cidx = self.cursor
        if name == 'pageup':
            self.move_cursor(x=cidx, y=(lidx - self._visible_height() + 1))
        elif name == 'pagedown':
            self.move_cursor(x=cidx, y=(lidx + self._visible_height() - 1))
        elif name == 'home':
            self.cursor = Cursor(0 if 'ctrl' in modifiers else lidx, 0)
        elif name == 'end':
            if 'ctrl' in modifiers:
                self.cursor = Cursor(
                    lidx=len(self.lines) - 1, cidx=len(self.lines[-1]) - 1)
            else:
                self.cursor = Cursor(lidx, len(self.lines[lidx]) - 1)
        elif name in ('left', 'right', 'up', 'down'):
            self.cursor = handle_arrow(
                cast(ArrowName, name), modifiers, self.lines, self.cursor)
        else:
            return False
        return True

    def _handle_cut_and_paste_keys(
            self, name: str, char: str, modifiers: set[str]):
        """Handle key combinations used for cutting and pasting."""
        if 'ctrl' not in modifiers:
            return False

        selection_before = self.selection_anchor
        if name == 'a':
            self.selection_anchor = Cursor(0, 0)
            self.cursor = Cursor(
                lidx=len(self.lines) - 1, cidx=len(self.lines[-1]) - 1)
        elif name in ('c', 'x'):
            if selection_before:
                lines, first, last = self._get_selected_lines(selection_before)
                lines[-1] = lines[-1][: last.cidx]
                lines[0] = lines[0][first.cidx :]
                self.clipboard = lines.copy()
                self.log(f'copied to clipboard: {self.clipboard}')
                if name == 'x':
                    self._delete_selection(first, last)
                    new_lidx = min(first.lidx, len(self.lines) - 1)
                    self.cursor = Cursor(
                        new_lidx, min(first.cidx,
                        len(self.lines[new_lidx]) - 1))
        elif name in ('u', 'v'):
            self._insert_clipboard_at_selection(selection_before, self.cursor)
        else:
            return False                                     # pragma: no cover
        return True

    def _handle_tab_key(self, name: str, char: str, modifiers: set[str]):
        """Handle the Tab key.

        This simply inserts 4 spaces.
        """
        if name == 'tab':
            for _ in range(4):
                self._insert_char(' ')
            return True
        else:
            return False

    def _handle_enter_key(self, name: str, char: str, modifiers: set[str]):
        """Handle the Enter (Return) key."""
        selection_before = self.selection_anchor
        if name != 'enter':
            return False

        old_lines, first, last = self._get_selected_lines(selection_before)
        head = f'{old_lines[0][:first.cidx]} '
        tail = f'{old_lines[-1][last.cidx:]}'
        if old_lines[0].isspace():
            indent = 0
        else:
            indent = len(old_lines[0]) - len(old_lines[0].lstrip())

        self.lines[first.lidx : last.lidx + 1] = [
            head, f'{" " * indent}{tail.lstrip() or " "}']
        self.cursor = Cursor(first.lidx + 1, min(first.cidx, indent))
        return True

    def _handle_deletion_keys(self, name: str, char: str, modifiers: set[str]):
        """Handle the backspace and delete keys."""
        selection_before = self.selection_anchor
        if name == 'delete':
            if selection_before is None:
                anchor = self.cursor
                cursor = handle_arrow(
                    'right', modifiers, self.lines, self.cursor)
            else:
                anchor = selection_before
                cursor = self.cursor
            self._delete_selection(anchor, cursor)

        elif name == 'backspace':
            if selection_before is None:
                anchor = self.cursor
                cursor = handle_arrow(
                    'left', modifiers, self.lines, self.cursor)
            else:
                anchor = selection_before
                cursor = self.cursor
            self._delete_selection(anchor, cursor)
        else:
            return False
        return True

    def watch_cursor(self) -> None:
        """Handle a change to the cursor position."""
        self._scroll_to_cursor()

    @property
    def content(self) -> RenderableType:
        """The editor content as a RenderableType."""
        syntax = Syntax(
            '\n'.join(self.lines), lexer='markdown', theme=self.theme)
        cursor = self.cursor
        if self.cursor_visible:
            syntax.stylize_range(
                'reverse', cursor.inc_line(1), cursor.inc(1, 1))
        if self.selection_anchor is not None:
            first = min(self.selection_anchor, self.cursor)
            second = max(self.selection_anchor, self.cursor)
            selection_style = Style(
                bgcolor=self.theme_colors.selection_bgcolor.rich_color)
            syntax.stylize_range(
                selection_style, first.inc_line(1), second.inc_line(1))
        return syntax

    def _scroll_to_cursor(self) -> None:
        self.post_message(
            TextAreaCursorMoved(self.cursor.cidx, self.cursor.lidx))

    def _visible_height(self) -> int:
        parent = self.parent
        return parent.window_region.height

    def _get_selected_lines(
        self,
        maybe_anchor: Cursor | None,
        maybe_cursor: Cursor | None = None,
    ) -> tuple[list[str], Cursor, Cursor]:
        """Collect the lines within the current selection.

        :return:
            A tuple of:

            - the lines between (inclusive) the optional selection anchor and
              the cursor,
            - the first of either the cursor or anchor
            - the last of either the cursor or anchor
        """
        cursor = maybe_cursor or self.cursor
        anchor = maybe_anchor or cursor
        first = min(anchor, cursor)
        last = max(anchor, cursor)
        return self.lines[first.lidx : last.lidx + 1], first, last

    def _insert_character_at_cursor(
            self, character: str, cursor: Cursor) -> None:
        line = self.lines[cursor.lidx]
        new_line = f'{line[:cursor.cidx]}{character}{line[cursor.cidx:]}'
        self.lines[cursor.lidx] = new_line

    def _delete_selection(self, anchor: Cursor, cursor: Cursor) -> None:
        old_lines, first, last = self._get_selected_lines(
            anchor, maybe_cursor=cursor)
        head = f'{old_lines[0][:first.cidx]}'
        tail = f'{old_lines[-1][last.cidx:]}'
        self.lines[first.lidx : last.lidx + 1] = [f'{head}{tail}']
        self.cursor = Cursor(first.lidx, first.cidx)

    def _insert_clipboard_at_selection(
            self, anchor: Cursor | None, cursor: Cursor) -> None:
        if anchor:
            self._delete_selection(anchor, cursor)
            cursor = self.cursor
        head = self.lines[cursor.lidx][: cursor.cidx]
        tail = self.lines[cursor.lidx][cursor.cidx :]
        if (clip_len := len(self.clipboard)) != 0:
            new_lines = self.clipboard.copy()
            new_lines[0] = f'{head}{new_lines[0]}'
            new_lines[-1] = f'{new_lines[-1]}{tail}'
            self.lines[cursor.lidx : cursor.lidx + 1] = new_lines
            self.cursor = Cursor(
                cursor.lidx + clip_len - 1,
                len(self.lines[cursor.lidx + clip_len - 1]) - len(tail),
            )

    def move_cursor(self, x: int, y: int) -> None:
        """Move the cursor to the given position."""
        self.cursor = self._get_valid_cursor(x, y)
        self.update(self.content)

    def _get_valid_cursor(self, x: int, y: int) -> Cursor:
        max_y = len(self.lines) - 1
        safe_y = max(0, min(max_y, y))
        max_x = len(self.lines[safe_y]) - 1
        safe_x = max(0, min(max_x, x))
        return Cursor(lidx=safe_y, cidx=safe_x)


class TextArea(ScrollableContainer, can_focus=True, can_focus_children=False):
    """
    A Widget that presents a feature-rich, multiline text editor interface.

    :theme:
        theme (str): Must be name of a Pygments style (https://pygments.org/styles/),
            e.g., "bw", "github-dark", "solarized-light".

    :kwargs:
        The standard Widget arguments.
    """

    DEFAULT_CSS = '''
    #validation_label {
        color: $error;
        text-style: italic;
        margin: 0 0 0 0;
    }
    '''
    text_input: TextInput

    def __init__(
            self, *args,
            on_changed: Callable[[list[str]], None],
            theme: str = 'github-dark',
            **kwargs):
        super().__init__(*args, **kwargs)
        self.theme = theme
        self.theme_colors = theme_name_to_colors(self.theme)
        self.on_changed = on_changed

    @property
    def lines(self) -> list[str]:
        """The editor's content as a list of strings."""
        return [line[:-1] for line in self.text_input.lines]

    @lines.setter
    def lines(self, contents: list[str]):
        self.text_input.move_cursor(0, 0)
        self.text_input.lines = [f'{line} ' for line in contents]
        if not self.text_input.lines:
            self.text_input.lines = [' ']

    def compose(self) -> ComposeResult:
        """Create this widget's sub-tree."""
        self.text_input = TextInput(
            theme=self.theme,
            theme_colors=self.theme_colors,
            on_changed=self.on_changed,
            id='editor_win')
        yield self.text_input

    def on_mount(self) -> None:
        """Handle the Mount event."""
        self.styles.background = self.theme_colors.bgcolor

    def on_focus(self) -> None:
        """Handle the Focus event."""
        self.text_input.focus()

    def on_text_area_cursor_moved(self, event: TextAreaCursorMoved) -> None:
        """Scroll the container so the cursor is visible."""
        def changed_val(new_val, old_val):
            if new_val != old_val:
                return new_val
            else:
                return None

        region = self.scrollable_content_region
        x_step = max(region.width // 6, 2)
        y_step = max(region.height // 6, 2)
        region_w = region.width
        region_h = region.height
        x, y = event.cursor_x, event.cursor_y
        scroll_x, scroll_y = self.scroll_x, self.scroll_y

        xt = None
        yt = None
        if x < scroll_x + x_step:
            xt = changed_val(max(0, x - x_step), scroll_x)
        elif x >= region_w + scroll_x - x_step:  # scroll right
            xt = changed_val(x - region_w + x_step, scroll_x)
        if y < scroll_y + y_step:  # scroll up
            yt = changed_val(max(0, y - y_step), scroll_y)
        elif y >= scroll_y + region_h - y_step:  # scroll down
            yt = changed_val(y - region_h + y_step, scroll_y)

        self.scroll_to(xt, yt, animate=False, force=True)
        self.text_input.update(self.text_input.content)


def handle_arrow(
        name: ArrowName, modifiers: set[str], lines: list[str], cursor: Cursor,
    ) -> Cursor:
    """Handle an arrow key."""
    handler = None
    if 'ctrl' in modifiers:
        handler = globals().get(f'_handle_ctrl_{name}')
    if handler is None:
        handler = globals().get(f'_handle_{name}')
    return handler(lines, cursor) if handler else cursor


def _handle_right(lines: list[str], cursor: Cursor) -> Cursor:
    max_x = len(lines[cursor.lidx]) - 1
    max_y = len(lines) - 1
    if cursor.lidx == max_y:
        return Cursor(lidx=max_y, cidx=min(max_x, cursor.cidx + 1))
    elif cursor.cidx == max_x:
        return Cursor(lidx=cursor.lidx + 1, cidx=0)
    else:
        return Cursor(lidx=cursor.lidx, cidx=cursor.cidx + 1)


def _handle_left(lines: list[str], cursor: Cursor) -> Cursor:
    if cursor.lidx == 0:
        return Cursor(0, cidx=max(0, cursor.cidx - 1))
    elif cursor.cidx == 0:
        return Cursor(
            lidx=cursor.lidx - 1,
            cidx=len(lines[cursor.lidx - 1]) - 1,
        )
    else:
        return Cursor(lidx=cursor.lidx, cidx=cursor.cidx - 1)


def _handle_down(lines: list[str], cursor: Cursor) -> Cursor:
    if cursor.lidx == len(lines) - 1:
        return cursor
    else:
        max_x = len(lines[cursor.lidx + 1]) - 1
        return Cursor(lidx=cursor.lidx + 1, cidx=min(max_x, cursor.cidx))


def _handle_up(lines: list[str], cursor: Cursor) -> Cursor:
    if cursor.lidx == 0:
        return cursor
    else:
        max_x = len(lines[cursor.lidx - 1]) - 1
        return Cursor(lidx=cursor.lidx - 1, cidx=min(max_x, cursor.cidx))


def _handle_ctrl_right(lines: list[str], cursor: Cursor) -> Cursor:
    max_x = len(lines[cursor.lidx]) - 1
    max_y = len(lines) - 1
    if cursor == (max_y, max_x):
        return cursor

    lidx, cidx = cursor
    if cidx == max_x:
        lidx, cidx = lidx + 1, 0
    tail = lines[lidx][cidx:]
    if match := r_word_boundary.match(tail):
        return Cursor(lidx=lidx, cidx=cidx + match.span()[1])
    else:  # no more words, move to end of line
        return Cursor(lidx=lidx, cidx=len(lines[lidx]) - 1)


def _handle_ctrl_left(lines: list[str], cursor: Cursor) -> Cursor:
    if cursor == (0, 0):
        return cursor

    lidx, cidx = cursor
    if cursor.cidx == 0:
        lidx, cidx = lidx - 1, len(lines[lidx - 1]) - 1
    tail = lines[lidx][:cidx][::-1]
    if match := r_word_boundary.match(tail):
        return Cursor(lidx=lidx, cidx=cidx - match.span()[1])
    else:  # no more words, move to start of line
        return Cursor(lidx=lidx, cidx=0)


def theme_name_to_colors(name: str) -> WidgetColors:
    """Create a `WidgetColors` instance from a theme name."""
    theme = PygmentsSyntaxTheme(name)
    bg_style = theme.get_background_style()
    t_color = Color.from_rich_color(cast(RichColor, bg_style.bgcolor))
    bgcolor = t_color
    if t_color.brightness >= 0.5:                               # noqa: PLR2004
        selection_bgcolor = t_color.darken(0.40)             # pragma: no cover
    else:
        selection_bgcolor = t_color.lighten(0.40)
    return WidgetColors(bgcolor, selection_bgcolor)
