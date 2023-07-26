"""Moving the selection using the keyboard.

The up and down keys change the currently selected (and highlighed) snippet.
"""
from __future__ import annotations
# pylint: disable=redefined-outer-name

import pytest

from support import clean_text, populate

long_infile_text = '''
    Main
      @text@
        Snippet 1
      @text@
        Snippet 2
      @text@
        Snippet 3
    Second
      @text@
        Snippet 4
      @text@
        Snippet 5
    Third
      @text@
        Snippet 6
      @text@
        Snippet 7
      @text@
        Snippet 8
      @text@
        Snippet 9
    Fourth
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


@pytest.fixture
def longfile(snippet_infile):
    """Create a standard input file for scrolling tests."""
    populate(snippet_infile, long_infile_text)
    return snippet_infile


# TODO: These pauses between moves should not be necessary. This must be a
#       Textual bug, possibly associated with the scrolling artifacts I have
#       encountered.
#
#       The pauses seem to provide some stability on my PC, but are really
#       only a sticking plaster.

def gen_moves(move, n):
    fast_n = 6
    moves_a = [move] * min(fast_n, n)
    moves_b = [move, 'pause:0.05'] * max(0, n - fast_n)
    return moves_a + moves_b


@pytest.mark.asyncio
@pytest.mark.parametrize("d_moves", [7, 13])
async def test_view_scrolls_as_necessary_on_down(
        longfile, snapshot_run, d_moves):
    """Moving down scrolls when necessary."""
    actions = (
        gen_moves('down', d_moves)            # Move a number of times.
    )
    _, snapshot_ok = await snapshot_run(longfile, actions, post_delay=0.10)
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
        + gen_moves('up', u_moves)            # Move up a number of times.
    )

    _, snapshot_ok = await snapshot_run(longfile, actions, post_delay=0.05)
    assert snapshot_ok
