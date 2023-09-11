"""Moving the snippets within and between gruops."""
from __future__ import annotations
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name

import pytest

from support import populate

std_infile_text = '''
    Group 1
      @text@
        Snippet 1
      @text@
        Snippet 2
      @text@
        Snippet 3
    Group 2
    Group 2: Sub G-2A
      @text@
        Snippet S2A-a
    Group 2: Sub G-2B
      @text@
        Snippet S2B-a
      @text@
        Snippet S2B-b
    Group 3
      @text@
        Snippet 4
      @text@
        Snippet 5
'''

single_group_text = '''
    Group 1
      @text@
        Snippet 1
      @text@
        Snippet 2
      @text@
        Snippet 3
'''


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


@pytest.fixture
def single_group_infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, single_group_text)
    return snippet_infile


class TestKeyboardControlled:
    """Using the keyboard as much as possible for group moves."""

    @pytest.mark.asyncio
    async def test_groups_fold_during_move(self, infile, snapshot_run):
        """The groups are collapsed during group moving."""
        actions = (
            ['left']              # Move to first group.
            + ['m']               # Start moving groups.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_groups_unfold_to_same_state_on_abort(
            self, infile, snapshot_run):
        """If a move is aborted the groups unfold to the same state.

        Already folded groups remain folded..
        """
        actions = (
            ['f']                 # Fold the first group.
            + ['left']            # Move to first group.
            + ['down'] * 3        # ... thence the fourth group.
            + ['f']               # ... fold that as well.
            + ['down']            # Move to the fith group.
            + ['m']               # Start folding.
            + ['up']              # Think about moving up a bit.
            + ['escape']          # ... then abort the move operation.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_first_group_moves_down_one_by_default(
            self, infile, snapshot_run):
        """First group initially gets position after second group."""
        actions = (
            ['left']              # Move to first group.
            + ['m']               # Start moving groups.
            + ['enter']           # Accept the default position
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_group_moves_up_one_by_default(
            self, infile, snapshot_run):
        """If possible the initial position is one group above."""
        actions = (
            ['left', 'down']      # Move to second group.
            + ['m']               # Start moving groups.
            + ['enter']           # Accept the default position
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_group_can_leave_a_subgroup(
            self, infile, snapshot_run):
        """A group can be moved out of a sub-group."""
        actions = (
            ['left']
            + ['down'] * 3        # Move to fourth group.
            + ['m']               # Start moving groups.
            + ['up']              # Move to insertion position.
            + ['enter']           # Complete the move.
            + ['right']           # Switch back to snippet.
            + ['enter']           # ... and add to the clipboard.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_group_can_be_moved_to_last_position(
            self, infile, snapshot_run):
        """A group can be moved to the very last position."""
        actions = (
            ['left']         # Move to first group.
            + ['m']          # Start move.
            + ['down'] * 10  # Move insertion indicator as far as possible.
            + ['enter']      # Finish the move.
            + ['right']      # Switch back to snippet.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_group_can_be_moved_to_last_position_in_group(
            self, infile, snapshot_run):
        """A group can be moved into the very last position in a group."""
        actions = (
            ['left']         # Move to first group.
            + ['m']          # Start move.
            + ['down'] * 2   # Move insertion indicator to end of second group
            + ['enter']      # Finish the move.
            + ['right']      # Switch back to snippet.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_indicator_length_clarifies_position(
            self, infile, snapshot_run):
        """The indicator's length distinguishes between group/sub-group."""
        actions = (
            ['left']              # Move to first group.
            + ['m']               # Start moving groups.
            + ['down'] * 3        # Move to below second group.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_single_group_cannot_move(
            self, single_group_infile, snapshot_run):
        """The indicator's length distinguishes between group/sub-group."""
        actions = (
            ['left']              # Move to first group.
            + ['m']               # Start moving groups.
        )
        _, snapshot_ok = await snapshot_run(single_group_infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'
