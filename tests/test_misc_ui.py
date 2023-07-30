"""Miscellaneous user interface behaviour."""
from __future__ import annotations
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name

import os
from pathlib import Path

import pytest

from support import populate

from clippets import core, snippets

HERE = Path(__file__).parent
std_infile_text = '''
    @title: Just testing.
    Main [tag-a tag-b]
      @text@
        Snippet 1
    Second [tag-b tag-c]
      @text@
        Snippet 2
    Second : Child A [tag-b]
      @md@
        Snippet A2
    Second : Child B [tag-b]
      @text@
        Snippet B2
    Third [tag-c tag-a]
      @text@
        Snippet 3
'''


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


class TestMouseControlled:
    """Mainly mouse based control."""

    @pytest.mark.asyncio
    async def test_the_snippet_under_the_mouse_is_highlighed(
            self, infile, snapshot_run):
        """When the mose is over a snippet, it is highlighted.

        The highlight is distinct from the added snippets.
        """
        actions = (
            ['left:snippet-1']            # Add Snippet 2 to clipboard.
            + ['hover:snippet-2']         # Hover over Snippet A2
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_selected_snippets_also_show_highlight(
            self, infile, snapshot_run):
        """When the mose is over am added snippet, it is highlighted.

        The highlight is distinct from the other added snippets.
        """
        actions = (
            ['left:snippet-1']            # Add Snippet 2 to clipboard.
            + ['left:snippet-3']          # Add Snippet B2 to clipboard.
            + ['hover:snippet-1']         # Hover over Snippet 2
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_highlight_disappears_as_necessary(
            self, infile, snapshot_run):
        """When the mose is over no snippet there is no highlight."""
        actions = (
            ['hover:group-3']            # Hover over Child A
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok
