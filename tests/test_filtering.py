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

from clippets import core, snippets

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
      @text@
        Snippet 4
'''


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
    """Using the mouse (mostly) to fold groups."""

    @pytest.mark.asyncio
    async def test_groups_can_be_folded(self, infile, snapshot_run):
        """Individual groups can be folded."""
        actions = (
            ['left:group-3']              # Fold the third group
            + ['left:group-5']            # Fold the fifth group
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

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
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_fold_can_move_selection(self, infile, snapshot_run):
        """The selection is moved if its group is folded."""
        actions = (
            ['left:group-1']              # Fold the first group, forcing the
                                          # selection to move.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_fold_can_move_selection_up(self, infile, snapshot_run):
        """The selection is moved up if a fold leaves no snippets below."""
        actions = (
            ['down'] * 4                  # Move to Snippet 3.
            + ['left:group-5']            # Fold the last group, forcing the
                                          # selection to move.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

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
        assert snapshot_ok, 'Snapshot does not match stored version'

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
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_nested_groups_can_be_folded(self, infile, snapshot_run):
        """Folding a group hides any child groups."""
        actions = (
            ['left:group-3']              # Fold the third (nested) group
            + ['left:group-2']            # Fold the second (parent) group
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

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
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "tag",
        ['a-0', 'a-1', 'b-0', 'b-1', 'b-2', 'b-3', 'c-0', 'c-1', 'c-2', 'c-3'])
    async def test_tags_can_be_used_to_fold(
            self, infile, snapshot_run, tag):
        """Clicking on a tag folds all groups with that tag."""
        actions = (
            [f'left:tag-tag-{tag}']     # Fold all tagged groups
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tag", ['a-0', 'b-1', 'c-0'])
    async def test_tags_reopen_closed_groups(
            self, infile, snapshot_run, tag):
        """Clicking on a tag re-opens all groups with that tag."""
        actions = (
            [f'left:tag-tag-{tag}']     # Fold all tagged groups
            + [f'left:tag-tag-{tag}']   # Fold all tagged groups
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_tags_open_if_partially_closed(self, infile, snapshot_run):
        """Clicking on a tag opens if any matching group is closed."""
        actions = (
            ['left:tag-tag-b-0']      # Fold all tag-b groups. This closes
                                      # some tag-c group.
            + ['left:tag-tag-c-3']    # Open all tag-c groups
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_f9_closes_unless_all_open(self, infile, snapshot_run):
        """The F9 closes if any group is not closed, even if hidden."""
        actions = (
            ['left:group-1']      # Fold first group.
            + ['left:group-3']    # Fold one (of two) child group.
            + ['left:group-2']    # Fold parent gruop
            + ['left:group-5']    # Fold laset gruop
            + ['f9']              # Close all remaining folds
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_f9_opens_if_all_manually_closed(self, infile, snapshot_run):
        """The F9 opens if all groups have been closes one-by-one."""
        actions = (
            ['left:group-1']      # Fold first group.
            + ['left:group-3']    # Fold one (of two) child group.
            + ['left:group-4']    # Fold one (of two) child group.
            + ['left:group-2']    # Fold parent gruop
            + ['left:group-5']    # Fold last gruop
            + ['f9']              # Open all folds
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'


class TestKeyboardControlled:
    """Using the keyboard (exclusively) to fold groups.

    Currently keyboard control is very limited in this area.
    """

    @pytest.mark.asyncio
    async def test_entire_tree_can_be_folded(self, infile, snapshot_run):
        """The F9 key toggle folding the entire tree."""
        actions = (
            ['f9']              # Fold the entire tree
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_entire_tree_can_be_expanded(self, infile, snapshot_run):
        """The F9 key toggle folding the entire tree."""
        actions = (
            ['f9']              # Fold the entire tree
            + ['f9']            # Expand the entire tree
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_groups_can_be_folded(self, infile, snapshot_run):
        """Individual groups can be folded."""
        actions = (
            ['left']                      # Select using groups.
            + ['down'] * 2                # Move to third group
            + ['f']                       # Close group.
            + ['down'] * 2                # Move to fifth group
            + ['f']                       # Close group.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_fold_works_when_snippet_selected(
            self, infile, snapshot_run):
        """A group can be folded when a snippet is selected."""
        actions = (
            ['left']                      # Select using groups.
            + ['down'] * 2                # Move to third group
            + ['f']                       # Close group.
            + ['down'] * 2                # Move to fifth group
            + ['right']                   # Move to snippet within group.
            + ['f']                       # Close group.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_unfold_reverts_snippet_selected(
            self, infile, snapshot_run):
        """Unfolding the same gruop, reverts to previous snippet selection."""
        actions = (
            ['left']                      # Select using groups.
            + ['down'] * 2                # Move to third group
            + ['f']                       # Close group.
            + ['down'] * 2                # Move to fifth group
            + ['right']                   # Move to snippet within group.
            + ['down']                    # Move to sedonc snippet in group.
            + ['f']                       # Close group.
            + ['f']                       # Reopen the group.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_ins_key_toggles_folds(self, infile, snapshot_run):
        """The Ins key also toggles folds."""
        actions = (
            ['left']                      # Select using groups.
            + ['down'] * 2                # Move to third group.
            + ['f']                       # Close group.
            + ['down'] * 2                # Move to fifth group.
            + ['insert']                  # Close group using Ins key.
            + ['up'] * 2                  # Move back to third group.
            + ['insert']                  # Re-open the third gruop.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_filter_field_down_selects_snippets(
            self, infile, snapshot_run):
        """The filter field provides a quick way to hide snippets."""
        actions = (
            ['ctrl+f']          # Switch to the filter field.
            + ['2']             # Select only snippets containting '2'.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_filter_ctrl_f_drops_focus(
            self, infile, snapshot_run):
        """The Ctrl+F key is used to switch back to snippet selection.

        The highlighted snippet will change if the previously highlighted
        snippet was hidden.
        """
        actions = (
            ['ctrl+f']          # Switch to the filter field.
            + ['2']             # Select only snippets containting '2'.
            + ['ctrl+f']        # Switch away from the filter field.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_filter_down_drops_focus(
            self, infile, snapshot_run):
        """The Down key switches back to snippet selection.

        The highlighted snippet will change if the previously highlighted
        snippet was hidden.
        """
        actions = (
            ['ctrl+f']          # Switch to the filter field.
            + ['2']             # Select only snippets containting '2'.
            + ['down']          # Switch away from the filter field.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_filter_up_drops_focus(
            self, infile, snapshot_run):
        """The Up key switches back to snippet selection.

        The highlighted snippet will change if the previously highlighted
        snippet was hidden.
        """
        actions = (
            ['ctrl+f']          # Switch to the filter field.
            + ['2']             # Select only snippets containting '2'.
            + ['up']            # Switch away from the filter field.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_filter_field_can_hide_everything(
            self, infile, snapshot_run):
        """All snippets will be hidden if nothing matches the filter."""
        actions = (
            ['ctrl+f']          # Switch to the filter field.
            + list('spam')      # Hide all the snippets.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_filter_ctrl_f_drops_focus_when_all_hidden(
            self, infile, snapshot_run):
        """The Ctrl+F key drops focus even when no snippet is visible."""
        actions = (
            ['ctrl+f']          # Switch to the filter field.
            + list('spam')      # Hide all the snippets.
            + ['ctrl+f']        # Switch away from the filter field.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_filter_ctrl_b_clears_the_filter(
            self, infile, snapshot_run):
        """The Ctrl+B key clears any actiove filter."""
        actions = (
            ['ctrl+f']          # Switch to the filter field.
            + list('spam')      # Hide all the snippets.
            + ['ctrl+f']        # Switch away from the filter field.
            + ['ctrl+b']        # Clear the filter.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_filter_uses_regular_expressions(
            self, infile, snapshot_run):
        """The filter is treated as a regular expression."""
        actions = (
            ['ctrl+f']          # Switch to the filter field.
            + list('[AB]')      # Select only snippets containting 'A' or 'B'.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_filter_malformed_re_falls_back_to_plaintext_matching(
            self, infile, snapshot_run):
        """A malformed regular expression is gracefully handled.

        It is actually treated as a simple strng match, allthough this will
        often cause all snippets to be hidden.
        """
        actions = (
            ['ctrl+f']          # Switch to the filter field.
            + list('[AB')       # Enter mal-formed expression.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'
