"""Application specific widgets."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from contextlib import suppress
from typing import Iterable

import rich.repr
from rich.style import Style
from rich.text import Span, Text
from textual import events
from textual.app import App
from textual.containers import Grid, VerticalScroll
from textual.keys import (
    REPLACED_KEYS, _character_to_key, _get_unicode_name_from_key)
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Label, Markdown, Static
from textual.widgets._markdown import MarkdownBlock

from .colors import keyword_colors

# We 'smuggle' keyword information by surrounding them with specific Unicode
# low quotes. These look quite like commas, making it extremely unlikely that
# anyone would would use them a snippet text.
re_keyword = re.compile('\u2e24([^\u2e25]*)\u2e25')
re_keyword_start = re.compile('\u2e24[^\u2e25]*')


class StdMixin:                        # pylint: disable=too-few-public-methods
    """Common code for various widgets."""

    def on_enter(self, _event):
        """Handle a mouse entering a widget."""
        self.app.update_hover(w=self)


class MyMarkdown(Markdown, StdMixin):
    """Application specific Markdown widget."""

    def on_click(self, event):
        """Process a mouse click."""
        if 'is_snippet' in self.classes:
            event.snippet = self


class MyText(Static, StdMixin):
    """Application specific Text widget."""

    def on_click(self, event):
        """Process a mouse click."""
        if 'is_snippet' in self.classes:
            event.snippet = self


class MyLabel(Label, StdMixin):
    """Application specific Label widget."""

    def on_click(self, event):
        """Process a mouse click."""
        if 'is_group' in self.classes:
            event.group = self


class MyTag(MyLabel):
    """A label indicating a snippet tag."""

    def on_click(self, event):
        """Process a mouse click."""
        event.tag = self


class MyVerticalScroll(VerticalScroll, StdMixin):
    """Application specific VerticalScroll widget."""


class MyInput(Input):
    """Application specific Input widget."""

    def on_blur(self, _event):
        """Process a mouse click."""
        self.app.handle_blur(self)


class SnippetMenu(ModalScreen):
    """Menu providing snippet action choices."""

    def compose(self):
        """Build the widget hierarchy."""
        yield Grid(
            Label('Choose action', id='question'),
            Button('Edit', variant='primary', id='edit'),
            Button('Duplicate', variant='primary', id='duplicate'),
            Button('Move', variant='primary', id='move'),
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

        for bindings in action_to_bindings.values():
            binding = bindings[0]
            if binding.key_display is None:
                key_display = self.app.get_key_display(binding.key)
                if key_display is None:
                    key_display = binding.key.upper()        # pragma: no cover
            else:
                key_display = binding.key_display            # pragma: no cover
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


def gen_highlight_spans(
        text: str, base_style: Style, off: int) -> tuple[list[Span], str]:
    """Split text into spans based on highlighting."""
    parts = re_keyword.split(text)
    spans = []
    new_parts = []
    for i, p in enumerate(parts):
        if i & 1:
            substr = p[1:]
            cc = p[0]
            color = keyword_colors.get(cc, 'green')
            style = base_style + Style(color=color)
        else:
            substr = re_keyword_start.sub('', p)
            substr = substr.replace('\u2e25(', '')
            style = base_style
        if substr:
            new_parts.append(substr)
            spans.append(Span(off, off + len(substr), style))
            off += len(substr)

    return spans, ''.join(new_parts)


def render_text(text: Text | str) -> Text:
    """Render specially marked up text."""
    if isinstance(text, str):
        text = Text(text, spans=[Span(0, len(text), Style())])
    raw_text = text.plain
    if '\u2e24' in raw_text:
        new_spans = []
        new_parts = []
        off = 0
        for span in text.spans:
            substr = raw_text[span.start:span.end]
            new_subspans, new_substr = gen_highlight_spans(
                substr, span.style, off)
            new_spans.extend(new_subspans)
            new_parts.append(new_substr)
            off += len(new_parts[-1])
        return Text(''.join(new_parts), spans=new_spans)
    else:
        return text


class ExtendMixin:
    """Namespace to hold ``textual`` extension methods."""

    def on_enter(self, ev):
        """Perform action the mouse enters the widtget."""
        with suppress(AttributeError):
            self.parent.on_enter(ev)

    def set_content(self, text: Text) -> None:
        """Over-ride set_content to highlight keywords."""
        self._text = render_text(text)
        self.update(self._text)

    async def _press_keys(self, keys: Iterable[str]) -> None:
        """Simulate a key press.

        This is a copy of the standrard Textual code except:

        - the 'wait:...' form of key is not handled; my test runner handles
          delays.
        - print calls have been removed.
        - assertions have been removed.
        - some wait calls have been removed.
        """
        app = self
        driver = app._driver                                     # noqa: SLF001
        for key in keys:
            if len(key) == 1 and not key.isalnum():
                key = _character_to_key(key)                    # noqa: PLW2901
            original_key = REPLACED_KEYS.get(key, key)
            char: str | None = None
            try:
                char = unicodedata.lookup(
                    _get_unicode_name_from_key(original_key))
            except KeyError:
                char = key if len(key) == 1 else None
            key_event = events.Key(key, char)
            key_event._set_sender(app)                           # noqa: SLF001
            driver.send_event(key_event)

        await app._animator.wait_until_complete()                # noqa: SLF001


MarkdownBlock.on_enter = ExtendMixin.on_enter
MarkdownBlock.set_content = ExtendMixin.set_content
App._press_keys = ExtendMixin._press_keys                        # noqa: SLF001
