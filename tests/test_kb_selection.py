"""Moving the selection using the keyboard.

The up and down keys change the currently selected (and highlighed) snippet.
"""
from __future__ import annotations
# pylint: disable=redefined-outer-name

import pytest

from support import long_infile_text, populate


@pytest.fixture
def longfile(snippet_infile):
    """Create a standard input file for scrolling tests."""
    populate(snippet_infile, long_infile_text)
    return snippet_infile


# TODO: Remove this when I am happy the code tests are stable.
def gen_moves(move, n):
    """Generate move and delay actions."""
    fast_n = 6
    moves_a = [move] * min(fast_n, n)
    # moves_b = [move, 'pause:0.01'] * max(0, n - fast_n)
    moves_b = [move] * max(0, n - fast_n)
    return moves_a + moves_b


@pytest.mark.asyncio
@pytest.mark.parametrize("d_moves", [7, 13])
async def test_view_scrolls_as_necessary_on_down(
        longfile, snapshot_run, d_moves):
    """Moving down scrolls when necessary."""
    actions = (
        gen_moves('down', d_moves)            # Move a number of times.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions, post_delay=0.15)
    assert snapshot_ok


@pytest.mark.asyncio
async def test_view_only_scrolls_down_as_necessary(longfile, snapshot_run):
    """Moving down only scrolls when necessary."""
    actions = (
        gen_moves('down', 6)                 # Move down a number of times.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok


@pytest.mark.asyncio
@pytest.mark.parametrize("d_moves, u_moves", [(7, 7), (13, 8)])
async def test_view_scrolls_as_necessary_on_up(
        longfile, snapshot_run, d_moves, u_moves):
    """Moving up scrolls when necessary."""
    actions = (
        gen_moves('down', d_moves)            # Move down number of times.
        # + ['pause:0.1']
        + gen_moves('up', u_moves)            # Move up a number of times.
        # + ['pause:0.1']
    )

    _, snapshot_ok = await snapshot_run(longfile, actions, post_delay=0.15)
    assert snapshot_ok


@pytest.mark.asyncio
async def test_move_down_skips_closed_groups(longfile, snapshot_run):
    """Closed groups are skipped when moving the selection down."""
    actions = (
        ['left:group-2']                   # close the second group.
        + ['down'] * 3                     # Move down to snippet 6.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok


@pytest.mark.asyncio
async def test_move_up_skips_closed_groups(longfile, snapshot_run):
    """Closed groups are skipped when moving the selection up."""
    actions = (
        ['down'] * 5                       # Move down to snippet 6.
        + ['left:group-2']                 # Close the second group.
        + ['up']                           # Move down to snippet 3.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions)
    assert snapshot_ok


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
    assert snapshot_ok
