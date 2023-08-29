"""Adding and removing snippet to and from the clipboard."""
from __future__ import annotations
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name

from pathlib import Path

import pytest

from support import populate

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
        assert snapshot_ok, 'Snapshot does not match stored version'

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
        assert snapshot_ok, 'Snapshot does not match stored version'

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
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_snippets_can_be_removed(
            self, infile, snapshot_run):
        """The mouse can also remove snippets rom the clipboard."""
        actions = (
            ['left:snippet-1']            # Add snippet 2
            + ['left:snippet-0']          # Then snippet 1
            + ['left:snippet-1']          # Add remove snippet 2
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_snippets_can_be_used_as_plaintext(
            self, infile, snapshot_run):
        """The '--raw option puts plaintext intot he clipboard."""
        actions = (
            ['left:snippet-1']            # Add snippet 2
            + ['left:snippet-0']          # Then snippet 1
        )
        _, snapshot_ok = await snapshot_run(infile, actions, options=['--raw'])
        assert snapshot_ok, 'Snapshot does not match stored version'


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
        assert snapshot_ok, 'Snapshot does not match stored version'

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
        assert snapshot_ok, 'Snapshot does not match stored version'

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
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_snippets_can_be_removed(
            self, infile, snapshot_run):
        """Already added snippets will be removed by the enter key."""
        actions = (
            ['down']                      # Add snippet 2
            + ['enter']
            + ['up']                      # Add snippet 1
            + ['enter']
            + ['down']                    # Remove snippet 2
            + ['enter']
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_f3_clears_the_clipboard(self, infile, snapshot_run):
        """The F3 key removes all clippets from the clipboard."""
        actions = (
            ['down']                      # Add snippet 2
            + ['enter']
            + ['up']                      # Add snippet 1
            + ['enter']
            + ['f3']                      # Then remove all snippets.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_the_clipboard_view_shows_a_scrollbar(
            self, infile, snapshot_run):
        """A scrollbar appeats in the clipboard view when required."""
        actions = (
            ['enter', 'down'] * 5         # Add snippets.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_the_clipboard_can_be_scrolled(
            self, infile, snapshot_run):
        """A scrollbar appeats in the clipboard view when required."""
        actions = (
            ['enter', 'down'] * 5         # Add snippets.
            + ['down:view'] * 5
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_group_ignores_add_group_order(
            self, infile, snapshot_run):
        """With selected group, adding is ignored (group order active)."""
        actions = (
            ['left']                      # Select group.
            + ['enter']                   # Try to add
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_group_ignores_add_insertion_order(
            self, infile, snapshot_run):
        """With selected group, adding is ignored (insertion order active)."""
        actions = (
            [ 'f8' ]                      # Switch to add/insertion order.
            + ['left']                    # Select group.
            + ['enter']                   # Try to add
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'
