"""Some patching og Textual classes.

This should be temporary, but that depend on me putting in the work to provide
pull requests.
"""
# mypy: ignore-errors
from __future__ import annotations

import unicodedata
from contextlib import suppress
from typing import Iterable, TYPE_CHECKING

from textual import events
from textual.app import App
from textual.keys import (
    REPLACED_KEYS, _character_to_key, _get_unicode_name_from_key)
from textual.widgets._markdown import MarkdownBlock

from .text import render_text

if TYPE_CHECKING:
    from rich.text import Text


class ExtendMixin:
    """Namespace to hold ``textual`` extension methods."""

    def on_enter(self, ev):
        """Perform action when the mouse enters the widtget."""
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
        if driver:
            for key in keys:
                if len(key) == 1 and not key.isalnum():
                    key = _character_to_key(key)                # noqa: PLW2901
                original_key = REPLACED_KEYS.get(key, key)
                char: str | None = None
                try:
                    char = unicodedata.lookup(
                        _get_unicode_name_from_key(original_key))
                except KeyError:                                # noqa: PERF203
                    char = key if len(key) == 1 else None
                key_event = events.Key(key, char)
                key_event._set_sender(app)                       # noqa: SLF001
                driver.send_event(key_event)

        await app._animator.wait_until_complete()                # noqa: SLF001

    MarkdownBlock.on_enter = on_enter
    MarkdownBlock.set_content = set_content
    App._press_keys = _press_keys                                # noqa: SLF001
