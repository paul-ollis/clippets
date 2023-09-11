"""Application specific widgets."""
from __future__ import annotations

from collections import defaultdict
from functools import partial
from typing import cast

import rich.repr
from rich.text import Text
from textual.color import Color
from textual.containers import Grid, VerticalScroll
from textual.screen import ModalScreen
from textual.validation import Function
from textual.widget import Widget
from textual.widgets import Button, Footer, Input, Label, Markdown, Static

from . import abc
from .snippets import Root, is_group


class AppChild(Widget):
    """Mixin for children of the Clippet's application class."""

    @property
    def app(self) -> abc.ClippetsApp:                  # type: ignore[override]
        """Handle a mouse entering a widget."""
        return cast(abc.ClippetsApp, super().app)


class StdMixin(AppChild):
    """Common code for various widgets."""

    def on_enter(self, _event):
        """Handle a mouse entering a widget."""
        self.app.update_hover(w=self)


class MyMarkdown(Markdown, StdMixin):
    """Application specific Markdown widget."""

    def on_click(self, event):
        """Process a mouse click."""
        if 'is_snippet' in self.classes:
            event.widget = self


class MyText(Static, StdMixin):
    """Application specific Text widget."""

    def on_click(self, event):
        """Process a mouse click."""
        if 'is_snippet' in self.classes:
            event.widget = self


class MyLabel(Label, StdMixin):
    """Application specific Label widget."""

    def on_click(self, event):
        """Process a mouse click."""
        if 'is_group' in self.classes:
            event.widget = self


class MyTag(MyLabel):                      # pylint: disable=too-many-ancestors
    """A label indicating a snippet tag."""

    def on_click(self, event):
        """Process a mouse click."""
        event.widget = self


class MyVerticalScroll(VerticalScroll, StdMixin):
    """Application specific VerticalScroll widget."""


class MyInput(Input, AppChild):
    """Application specific Input widget."""

    def on_blur(self, _event):
        """Process a mouse click."""
        self.app.handle_blur(self)


class PopupDialog(ModalScreen):
    """Base for 'popup' dialogues."""

    DEFAULT_CSS = '''
    #dialog {
        grid-rows: 1 3;
        grid-gutter: 1 2;
        padding: 0 1;
        height: auto;
        border: solid $primary-lighten-3;
        margin: 0 8 0 8;
        background: $surface;
        align: center middle;
    }
    #question {
        height: 1;
        width: 1fr;
        content-align: center middle;
    }
    '''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_class('popup')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Process a mouse click on a button."""
        self.dismiss(event.button.id)


class GreyoutScreen(PopupDialog):
    """Screen to grey out the current screen."""

    def __init__(self, message: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message

    def compose(self):
        """Build the widget hierarchy."""
        styles = self.styles
        bg = styles.background
        styles.background = Color(bg.r, bg.g, bg.b, a=0.6)

        yield Static(self.message, classes='modal_information')


class SnippetMenu(PopupDialog):
    """Menu providing snippet action choices."""

    AUTO_FOCUS = '#add_snippet'
    DEFAULT_CSS = PopupDialog.DEFAULT_CSS + '''
    .popup {
        grid-size: 5;
    }
    .question {
        column-span: 5;
    }
    '''

    def compose(self):
        """Build the widget hierarchy."""
        styles = self.styles
        bg = styles.background
        styles.background = Color(bg.r, bg.g, bg.b, a=0.6)

        yield Grid(
            Label('Choose action', id='question', classes='question'),
            Button('Add', variant='primary', id='add_snippet'),
            Button('Edit', variant='primary', id='edit'),
            Button('Duplicate', variant='primary', id='duplicate'),
            Button('Move', variant='primary', id='move'),
            Button('Cancel', variant='primary', id='cancel'),
            id='dialog', classes='popup',
        )


class GroupMenu(PopupDialog):
    """Menu providing group action choices."""

    AUTO_FOCUS = '#add_snippet'
    DEFAULT_CSS = PopupDialog.DEFAULT_CSS + '''
    .popup {
        grid-size: 4;
    }
    .question {
        column-span: 4;
    }
    '''

    def compose(self):
        """Build the widget hierarchy."""
        styles = self.styles
        bg = styles.background
        styles.background = Color(bg.r, bg.g, bg.b, a=0.6)

        yield Grid(
            Label('Choose action', id='question', classes='question'),
            Button('Add snippet', variant='primary', id='add_snippet'),
            Button('Add group', variant='primary', id='add_group'),
            Button('Rename', variant='primary', id='rename_group'),
            Button('Cancel', variant='primary', id='cancel'),
            id='dialog', classes='popup',
        )


class GroupNameMenu(PopupDialog):
    """Popup to enter the name of a new group."""

    AUTO_FOCUS = '#field_input'
    DEFAULT_CSS = PopupDialog.DEFAULT_CSS + '''
    #dialog {
        grid-rows: 3 3;
        grid-gutter: 1 2;
        padding: 0 1;
        height: auto;
        border: solid $primary-lighten-3;
        margin: 0 8 0 8;
        background: $surface;
        align: center middle;
    }
    .popup {
        grid-size: 2 2;
        align: center middle;
    }
    .field_input {
        column-span: 2;
    }
    '''

    def __init__(
            self, message: str, root: Root, orig_name: str = '',
            *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message
        self.root = root
        self.yes_buttons: list[Button] = []
        self.group_name: str = ''
        self.orig_name = orig_name

    def compose(self):
        """Build the widget hierarchy."""
        bg = self.styles.background
        styles = self.styles
        styles.background = Color(bg.r, bg.g, bg.b, a=0.6)
        if self.orig_name:
            b1 = Button('OK', variant='primary', id='add_below')
        else:
            b1 = Button('Add below', variant='primary', id='add_below')
        b2 = Button('Cancel', variant='primary', id='cancel')
        self.yes_buttons.extend([b1])
        input = partial(
            Input, id='field_input', classes='field_input',
            validators=[
                Function(self.is_unique, 'Not a valid and unique name')])
        if self.orig_name:
            input = partial(input, self.orig_name)
        else:
            input = partial(input, placeholder='Unique group name')
        for b in self.yes_buttons:
            b.disabled = True
        yield Grid(input(), b1, b2, id='dialog', classes='popup freddy')

    def is_unique(self, name):
        """Check if the name is legal and unique."""
        name = name.strip()
        ok = bool(name)
        for group in self.root.walk(is_group):
            if group.name == name and name != self.orig_name:
                ok = False
                break
        for b in self.yes_buttons:
            b.disabled = not ok
        self.group_name = name if ok else ''
        return True


class FileChangedMenu(PopupDialog):
    """Popup for when the snippets file has been changed."""

    AUTO_FOCUS = '#load'
    DEFAULT_CSS = PopupDialog.DEFAULT_CSS + '''
    .popup {
        grid-size: 2;
    }
    .question {
        column-span: 2;
    }
    '''

    def compose(self):
        """Build the widget hierarchy."""
        bg = self.styles.background
        styles = self.styles
        styles.background = Color(bg.r, bg.g, bg.b, a=0.6)
        yield Grid(
            Label(
                'Input file has changed.', id='question', classes='question'),
            Button('Load changes', variant='primary', id='load'),
            Button('Ignore', variant='primary', id='cancel'),
            id='dialog', classes='popup')


class DefaulFileMenu(PopupDialog):
    """Popup for when starting with a non-existant file."""

    AUTO_FOCUS = '#create'
    DEFAULT_CSS = PopupDialog.DEFAULT_CSS + '''
    .popup {
        grid-size: 2;
    }
    .question {
        column-span: 2;
    }
    '''

    def __init__(self, filename, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filename = filename

    def compose(self):
        """Build the widget hierarchy."""
        bg = self.styles.background
        styles = self.styles
        styles.background = Color(bg.r, bg.g, bg.b, a=0.6)
        yield Grid(
            Label(
                f'File {self.filename} does not exist, choose:',
                id='question', classes='question'),
            Button('Create', variant='primary', id='create'),
            Button('Quit', variant='primary', id='quit'),
            id='dialog', classes='popup')


@rich.repr.auto
class MyFooter(Footer, AppChild):
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
