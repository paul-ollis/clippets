"""Abstract base classes to help clean type checking."""
# ruff: noqa: D102
# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# type: ignore[empty-body]

from textual.app import Binding
from textual.widget import Widget


class ClippetsApp:
    """Abstract base class for core.Clippets."""

    def active_shown_bindings(self) -> list[Binding]:
        return []

    def context_name(self) -> str:
        return ''

    def get_key_display(self, key: str) -> str:
        return ''

    def handle_blur(self, w:  Widget) -> None:
        ...

    def update_hover(self, w) -> None:
        ...
