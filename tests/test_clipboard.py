"""Adding and removing snippet to and from the clipboard."""
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
    Main [tag-a tag-b]
      @md@
        Markdown allows:

        - *Italic* text.
        - **Bold** text.
        - ***Bold italic*** text.

    Second [tag-b tag-c]
      @md@
        Snippet 2
    Second : Child A [tag-b]
      @md@
        Snippet A2
    Second : Child B [tag-b]
      @md@
        Snippet B2
    Third [tag-c tag-a]
      @md@
        Snippet 3
'''


@pytest.fixture(autouse=True)
def set_env():
    """Set up the environment for these tests."""
    os.environ['CLIPPETS_EDITOR'] = f'python {HERE / "edit_helper.py"}'


@pytest.fixture(autouse=True)
def reset_app_data():
    """Reset some application data.

    This ensures that snippet/widget IDs can be predicted.
    """
    snippets.reset_for_tests()
    core.reset_for_tests()


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


class TestMouseControlled:
    """Using the mouse (mostly) to populate the clipboard."""

    @pytest.mark.asyncio
    async def test_snippets_use_group_order_by_default(
            self, infile, snapshot_run):
        """By default snippets show in the order thery appear in groups."""
        actions = (
            ['left:snippet-1']            # Add snippet 2
            + ['left:snippet-0']          # Then snippet 1
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_f8_switches_to_insertion_order(
            self, infile, snapshot_run):
        """Pressing F8 will switch to show snippets in insertion order."""
        actions = (
            ['left:snippet-1']            # Add snippet 2
            + ['left:snippet-0']          # Then snippet 1
            + ['f8']                      # Then toggle the order
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_f8_acts_as_a_toggle(
            self, infile, snapshot_run):
        """The F8 key toggles back to the group order."""
        actions = (
            ['left:snippet-1']            # Add snippet 2
            + ['left:snippet-0']          # Then snippet 1
            + ['f8']                      # Then toggle the order
            + ['f8']                      # Then toggle it back
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok


class TestKeyboardControlled:
    """Using the keyboard (mostly) to populate the clipboard."""

    @pytest.mark.asyncio
    async def test_snippets_use_group_order_by_default(
            self, infile, snapshot_run):
        """By default snippets show in the order thery appear in groups."""
        actions = (
            ['down']                      # Add snippet 2
            + ['enter']
            + ['up']                      # Add snippet 1
            + ['enter']
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_f8_switches_to_insertion_order(
            self, infile, snapshot_run):
        """Pressing F8 will switch to show snippets in insertion order."""
        actions = (
            ['down']                      # Add snippet 2
            + ['enter']
            + ['up']                      # Add snippet 1
            + ['enter']
            + ['f8']                      # Then toggle the order
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_f8_acts_as_a_toggle(
            self, infile, snapshot_run):
        """The F8 key toggles back to the group order."""
        actions = (
            ['down']                      # Add snippet 2
            + ['enter']
            + ['up']                      # Add snippet 1
            + ['enter']
            + ['f8']                      # Then toggle the order
            + ['f8']                      # Then toggle it back
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_the_clipboard_view_shows_a_scrollbar(
            self, infile, snapshot_run):
        """A scrollbar appeats in the clipboard view when required."""
        actions = (
            ['enter', 'down'] * 5         # Add snippets.
        )
        _, snapshot_ok = await snapshot_run(infile, actions, post_delay=0.05)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_the_clipboard_can_be_scrolled(
            self, infile, snapshot_run):
        """A scrollbar appeats in the clipboard view when required."""
        actions = (
            ['enter', 'down'] * 5         # Add snippets.
            + ['down:view'] * 5
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok
