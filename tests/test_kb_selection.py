"""Moving the selection using the keyboard.

The up and down keys change the currently selected (and highlighed) snippet.
"""
from __future__ import annotations
# pylint: disable=redefined-outer-name

import pytest

from support import long_infile_text, populate

nested_infile_text = '''
    Main
      @text@
        Snippet 1
      @text@
        Snippet 2
      @text@
        Snippet 3
    Main : Level 1
    Main : Level 1: Level 2
      @text@
        Snippet 4
      @text@
        Snippet 5
      @text@
        Snippet 6
      @text@
        Snippet 7
      @text@
        Snippet 8
      @text@
        Snippet 9
    Main : Level 1: Level 2B
      @text@
        Snippet 10
      @text@
        Snippet 11
      @text@
        Snippet 12
      @text@
        Snippet 13
      @text@
        Snippet 14
'''

extended_nested_infile_text = nested_infile_text + '''
    Second
      @text@
        Snippet 1
      @text@
        Snippet 2
      @text@
        Snippet 3
'''

@pytest.fixture
def longfile(snippet_infile):
    """Create a standard input file for scrolling tests."""
    populate(snippet_infile, long_infile_text)
    return snippet_infile


@pytest.fixture
def nested_file(snippet_infile):
    """Create a standard input file for scrolling tests."""
    populate(snippet_infile, nested_infile_text)
    return snippet_infile


@pytest.fixture
def ext_nested_file(snippet_infile):
    """Create a standard input file for scrolling tests."""
    populate(snippet_infile, extended_nested_infile_text)
    return snippet_infile


@pytest.mark.asyncio
@pytest.mark.parametrize("d_moves", [7, 13])
async def test_view_scrolls_as_necessary_on_down(
        longfile, snapshot_run, d_moves):
    """Moving down scrolls when necessary."""
    actions = (
        ['down'] * d_moves                 # Move down a number of times.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_view_only_scrolls_down_as_necessary(longfile, snapshot_run):
    """Moving down only scrolls when necessary."""
    actions = (
        ['down'] * 6                       # Move down a number of times.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
@pytest.mark.parametrize("d_moves, u_moves", [(7, 7), (13, 8)])
async def test_view_scrolls_as_necessary_on_up(
        longfile, snapshot_run, d_moves, u_moves):
    """Moving up scrolls when necessary."""
    actions = (
        ['down'] * d_moves                 # Move down a number of times.
        + ['up'] * u_moves                 # Move up a number of times.
    )

    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_move_down_skips_closed_groups(longfile, snapshot_run):
    """Closed groups are skipped when moving the selection down."""
    actions = (
        ['left:group-2']                   # close the second group.
        + ['down'] * 3                     # Move down to snippet 6.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_move_up_skips_closed_groups(longfile, snapshot_run):
    """Closed groups are skipped when moving the selection up."""
    actions = (
        ['down'] * 5                       # Move down to snippet 6.
        + ['left:group-2']                 # Close the second group.
        + ['up']                           # Move down to snippet 3.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_no_snippets_is_handled(longfile, snapshot_run):
    """An input with no snippets is gracefully handled."""
    populate(longfile, '''
        Main
    ''')
    actions = (
        ['down']                           # Try to move down.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_left_moves_to_group_names(longfile, snapshot_run):
    """The left key moves into the group names."""
    actions = (
        ['left']                           # Move into the group names.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_left_stops_within_groups(longfile, snapshot_run):
    """The left is ignore when already in the groups."""
    actions = (
        ['left']                           # Move into the group names.
        + ['left']                         # Pressing again does nothing.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_right_stops_within_snippets(longfile, snapshot_run):
    """The right is ignore when already in the snippets."""
    actions = (
        ['right']                          # Try to move righ in snippets.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_down_moves_within_groups_and_scrolls(longfile, snapshot_run):
    """The down key moves within the group names."""
    actions = (
        ['left']                           # Move into the group names.
        + ['down'] * 3                     # Move to the last group.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_down_skip_hidden_groups(ext_nested_file, snapshot_run):
    """The down key skips over hidden (by folding) names."""
    actions = (
        ['left']                           # Move into the group names.
        + ['f9']                           # Close all groups.
        + ['down']                         # Move to the last group.
    )
    _, snapshot_ok = await snapshot_run(ext_nested_file, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_unfold_after_group_move_scrolls(ext_nested_file, snapshot_run):
    """Unfolding after a move, will scroll as required."""
    actions = (
        ['left']                           # Move into the group names.
        + ['f9']                           # Close all groups.
        + ['down']                         # Move to the last group.
        + ['f9']                           # Close all groups.
    )
    _, snapshot_ok = await snapshot_run(ext_nested_file, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_up_moves_within_groups(longfile, snapshot_run):
    """The up key moves within the group names."""
    actions = (
        ['left']                           # Move into the group names.
        + ['down'] * 3                     # Move to the last group.
        + ['up'] * 2                       # Move to the second group.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_down_stops_at_last_gruop(longfile, snapshot_run):
    """The up key safely hits the bottom."""
    actions = (
        ['left']                           # Move into the group names.
        + ['down'] * 3                     # Move to the last group.
        + ['down'] * 2                     # Try to move beyond.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_up_stops_at_first_group(longfile, snapshot_run):
    """The up key safely hits the top."""
    actions = (
        ['left']                           # Move into the group names.
        + ['down'] * 3                     # Move to the last group.
        + ['up'] * 3                       # Move to the first group.
        + ['up'] * 2                       # Try to move beyond.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_left_then_right_keeps_snippet_section(longfile, snapshot_run):
    """Moving right again selects the same snippet as before."""
    actions = (
        ['down'] * 2                       # Move down a number of times.
        + ['left']                         # Move into the group names.
        + ['right']                        # Move back to the seleced snippet.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_first_snippet_selected_when_group_is_changed(
            longfile, snapshot_run):
    """When moving right in a new group, the first snippet is selected."""
    actions = (
        ['down'] * 2                       # Move down a number of times.
        + ['left']                         # Move into the group names.
        + ['down'] * 2                     # Move down 2 groups.
        + ['right']                        # To first snippet in this group.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_closing_group_with_mouse_keeps_selection_in_groups(
            nested_file, snapshot_run):
    """Closing a group using the mouse leaves the selection within groups."""
    actions = (
        ['left']                           # Move to group 1.
        + ['left:group-3']                 # Close the third group.
    )
    _, snapshot_ok = await snapshot_run(nested_file, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_cannot_enter_zero_snippet_group(
            nested_file, snapshot_run):
    """Right key does nothing if the group has no snippets."""
    actions = (
        ['left']                           # Move to group 1.
        + ['left:group-3']                 # Close the third group.
        + ['down']                         # Move to group 2
        + ['right']                        # Try to enter it.
    )
    _, snapshot_ok = await snapshot_run(nested_file, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_cannot_enter_closed_group(
            nested_file, snapshot_run):
    """Right key does nothing if the group is closed."""
    actions = (
        ['left']                           # Move to group 1.
        + ['left:group-3']                 # Close the third group.
        + ['down'] * 2                     # Move to group 3
        + ['right']                        # Try to enter it.
    )
    _, snapshot_ok = await snapshot_run(nested_file, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_open_groups_can_be_entered(
            nested_file, snapshot_run):
    """Open groups can be entered."""
    actions = (
        ['left']                           # Move to group 1.
        + ['left:group-3']                 # Close the third group.
        + ['down'] * 3                     # Move to group 4
        + ['right']                        # Enter it.
    )
    _, snapshot_ok = await snapshot_run(nested_file, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'
