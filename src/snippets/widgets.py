"""Application specific widgets."""

import re
from collections import defaultdict
from contextlib import suppress
from typing import ClassVar, Optional

import rich.repr
from rich.style import Style
from rich.text import Span, Text
from rich.console import RenderableType
from textual import events
from textual.app import Binding
from textual.containers import Grid, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Footer, Input, Label, Markdown, Static
from textual.widgets._markdown import MarkdownBlock

from .colors import keyword_colors

# We 'smuggle' keyword information by surrounding them with specific Unicode
# low quotes. These look quite like commas, making is extremely unlikely that
# anyone would would use them a snippet text.
re_keyword = re.compile('\u2e24([^\u2e25]*)\u2e25')


class StdMixin:
    """Common code for various widgets."""

    def on_enter(self, _ev):
        """Handle a mouse entering a widget."""
        self.app.update_hover(w=self)


class MyMarkdown(Markdown, StdMixin):
    """Application specific Markdown widget."""

    def on_click(self, ev):
        """Process a mouse click."""
        if 'is_snippet' in self.classes:
            #@ print(f'CLICK[{self.__class__.__name__}]: {ev=}')
            ev.snippet = self


class MyText(Static, StdMixin):
    """Application specific Text widget."""

    def on_click(self, ev):
        """Process a mouse click."""
        if 'is_snippet' in self.classes:
            #@ print(f'CLICK[{self.__class__.__name__}]: {ev=}')
            ev.snippet = self


class MyLabel(Label, StdMixin):
    """Application specific Label widget."""

    def on_click(self, ev):
        """Process a mouse click."""
        if 'is_group' in self.classes:
            ev.group = self


class MyTag(MyLabel):
    """A label indicating a snippet tag."""

    def on_click(self, ev):
        """Process a mouse click."""
        ev.tag = self


class MyVerticalScroll(VerticalScroll, StdMixin):
    """Application specific VerticalScroll widget."""


class MyInput(Input):
    """Application specific Input widget."""


class SnippetMenu(ModalScreen):
    """Menu providing snippet action choices."""

    BINDINGS = [
        Binding('q', 'request_quit', 'Exit help'),
    ]

    def compose(self):
        """Build the widget hierarchy."""
        yield Grid(
            Label('Choose action', id='question'),
            Button('Edit', variant='primary', id='edit'),
            Button('Duplicate', variant='primary', id='duplicate'),
            Button('Cancel', variant='primary', id='cancel'),
            id='dialog',
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Process a mouse click on a button."""
        self.dismiss(event.button.id)


@rich.repr.auto
class MyFooter(Footer):
    """A simple footer docked to the bottom of the parent container."""

    def __init__(self) -> None:
        super().__init__()
        self._context = self.app.context_name()

    def check_context(self):
        """Check whether the appliation context has changed."""
        new_name = self.app.context_name()
        if new_name != self._context:
            self._context = new_name
            self._bindings_changed(self)

    def _make_key_text(self) -> Text:
        """Create text containing all the keys."""
        base_style = self.rich_style
        text = Text(
            style=self.rich_style,
            no_wrap=True,
            overflow='ellipsis',
            justify='left',
            end='',
        )
        highlight_style = self.get_component_rich_style('footer--highlight')
        highlight_key_style = self.get_component_rich_style(
            'footer--highlight-key')
        key_style = self.get_component_rich_style('footer--key')
        description_style = self.get_component_rich_style(
            'footer--description')

        bindings = self.app.active_shown_bindings()
        action_to_bindings = defaultdict(list)
        for binding in bindings:
            action_to_bindings[binding.action].append(binding)

        for _, bindings in action_to_bindings.items():
            binding = bindings[0]
            if binding.key_display is None:
                key_display = self.app.get_key_display(binding.key)
                if key_display is None:
                    key_display = binding.key.upper()
            else:
                key_display = binding.key_display
            hovered = self.highlight_key == binding.key
            key_text = Text.assemble(
                (
                    f' {key_display} ',
                    highlight_key_style if hovered else key_style),
                (
                    f' {binding.description} ',
                    highlight_style if hovered
                        else base_style + description_style,
                ),
                meta={
                    '@click': f'app.check_bindings("{binding.key}")',
                    'key': binding.key,
                },
            )
            text.append_text(key_text)
        return text


class Extend:
    """Namespace to hold ``textual`` extension methods."""

    def on_enter(self, ev):
        """Perform action the mouse enters the widtget."""
        with suppress(AttributeError):
            self.parent.on_enter(ev)

    def set_content(self, text: Text) -> None:
        """Over-ride set_content to highlight keywords."""
        def trim_spans(off, n):
            for i, span in enumerate(spans):
                a, b, style = span
                if a > off:
                    a -= n
                if b > off:
                    b -= n
                spans[i] = Span(a, b, style)

        if '\u2e24' in text.plain:
            text = text.copy()
            parts = re_keyword.split(text.plain)
            new_parts = []
            off = 0
            spans = text.spans
            for i, p in enumerate(parts):
                if i & 1:
                    new_parts.append(p[1:])
                    cc = p[0]
                    trim_spans(off, 2)
                    off += len(p) - 1
                    trim_spans(off, 1)
                    spans.append(Span(
                        off - len(p) + 1, off,
                        Style(color=keyword_colors.get(cc, 'green'))))
                else:
                    new_parts.append(p)
                    off += len(p)
            text._text = [''.join(new_parts)]                    # noqa: SLF001
            text.spans = spans
        self._text = text
        self.update(text)


MarkdownBlock.on_enter = Extend.on_enter
MarkdownBlock.set_content = Extend.set_content
