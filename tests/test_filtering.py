"""Filtering and folding up groups.

- The filter input at the top of the screen can be used to show only snippets
  containg certain strings.

- Each group can be individually folded.

- Group tags can be used to fold multipl groups at once.

- The entire tree can be folded.
"""
from __future__ import annotations
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name

import os
from pathlib import Path

import pytest

from support import populate

from clippets import snippets

HERE = Path(__file__).parent
std_infile_text = '''
    Main [tag-a tag-b]
      @text@
        Snippet 1
    Second [tag-b tag-c]
      @text@
        Snippet 2
    Second : Child A [tag-b]
      @text@
        Snippet A2
    Second : Child B [tag-b]
      @text@
        Snippet B2
    Third [tag-c tag-a]
      @text@
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


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


class TestMouseControlled:
    """Using the mouse (mostly) to fold groups."""

    # pylint: disable=too-few-public-methods

    @pytest.mark.asyncio
    async def test_groups_can_be_folded(self, infile, snapshot_run):
        """Individual groups can be folded."""
        actions = (
            ['left:group-3']              # Fold the third group
            + ['left:group-5']            # Fold the fifth group
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_groups_can_be_opened(self, infile, snapshot_run):
        """Individual groups can be opened."""
        actions = (
            ['left:group-3']              # Fold the third group
            + ['left:group-5']            # Fold the fifth group
            + ['left:group-3']            # Open the third group
            + ['left:group-5']            # Open the fifth group
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_fold_can_move_selection(self, infile, snapshot_run):
        """The selection is moved if its group is folded."""
        actions = (
            ['left:group-1']              # Fold the first group, forcing the
                                          # selection to move.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_open_can_move_selection(self, infile, snapshot_run):
        """The selection can be restored if its group is re-opened."""
        actions = (
            ['left:group-1']              # Fold the first group, forcing the
                                          # selection to move.
            + ['left:group-1']            # Re-open the first group, allowing
                                          # the selection to be restored.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_sel_move_kills_restore(self, infile, snapshot_run):
        """The selection is be restored if the user moves the selection."""
        actions = (
            ['left:group-1']              # Fold the first group, forcing the
                                          # selection to move.
            + ['down']                    # Manually move the selection.
            + ['left:group-1']            # Re-open the first group, allowing
                                          # the selection to be restored.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_nested_groups_can_be_folded(self, infile, snapshot_run):
        """Folding a group hides any child groups."""
        actions = (
            ['left:group-3']              # Fold the third (nested) group
            + ['left:group-2']            # Fold the second (parent) group
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_nested_group_fold_state_is_preserved(
            self, infile, snapshot_run):
        """Folding a group, leaves nested group folds unaffected."""
        actions = (
            ['left:group-3']              # Fold the third (nested) group
            + ['left:group-2']            # Fold the second (parent) group
            + ['left:group-2']            # Re-open the parent group
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok


class TestKeyboardControlled:
    """Using the keyboard (exclusively) to fold groups."""

    @pytest.mark.asyncio
    async def test_entire_tree_can_be_folded(self, infile, snapshot_run):
        """The F9 key toggle folding the entire tree."""
        actions = (
            ['f9']              # Fold the entire tree
        )
        runner, snapshot_ok = await snapshot_run(infile, actions)
        for w in runner.app.walk():
            print(w.uid())

        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_entire_tree_can_be_expanded(self, infile, snapshot_run):
        """The F9 key toggle folding the entire tree."""
        actions = (
            ['f9']              # Fold the entire tree
            + ['f9']            # Expand the entire tree
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok
