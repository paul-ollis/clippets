"""Moving the snippets within and between gruops."""
from __future__ import annotations
# pylint: disable=redefined-outer-name

import pytest

from support import clean_text, populate

std_infile_text = '''
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
      @text@
        Snippet 6
      @text@
        Snippet 7
'''
group_of_one_text = '''
    Main
      @text@
        Snippet 1
      @text@
        Snippet 2
    Second
      @text@
        Snippet 3
    Third
      @text@
        Snippet 4
      @text@
        Snippet 5
'''
empty_group_text = '''
    Main
      @text@
        Snippet 1
      @text@
        Snippet 2
      @text@
        Snippet 3
    Second
    Third
      @text@
        Snippet 4
      @text@
        Snippet 5
'''


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


@pytest.fixture
def infile_g1(snippet_infile):
    """Create a input file with a single entry group."""
    populate(snippet_infile, group_of_one_text)
    return snippet_infile


@pytest.fixture
def infile_g0(snippet_infile):
    """Create a input file with an empty group."""
    populate(snippet_infile, empty_group_text)
    return snippet_infile


@pytest.fixture(params=range(7))
def n_moves(request) -> list:
    """Generate fixtures for various numbers of moves."""
    return request.param


@pytest.mark.asyncio
async def test_move_snippet_within_group(infile, snapshot_run):
    """A snippet may be moved within a group."""
    actions = (
        ['down'] * 5          # Move to Snippet 6
        + ['m']               # Start moving
        + ['enter']           # Complete move
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Snippet: 'Snippet 3'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 4'
        Snippet: 'Snippet 6'
        Snippet: 'Snippet 5'
        Snippet: 'Snippet 7'
    ''')
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.groups.full_repr()
    assert snapshot_ok


@pytest.mark.asyncio
async def test_move_snippet_to_start_of_group(infile, snapshot_run):
    """A snippet may be moved to the start of a group."""
    actions = (
        ['down'] * 5          # Move to Snippet 6
        + ['m']               # Start moving
        + ['up'] * 1          # Move insertion above snippet 4
        + ['enter']           # Complete move
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Snippet: 'Snippet 3'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 6'
        Snippet: 'Snippet 4'
        Snippet: 'Snippet 5'
        Snippet: 'Snippet 7'
    ''')
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.groups.full_repr()
    assert snapshot_ok


@pytest.mark.asyncio
async def test_move_snippet_to_end_of_group(infile, snapshot_run):
    """A snippet may be moved to the end of a group."""
    actions = (
        ['down'] * 5          # Move to Snippet 6
        + ['m']               # Start moving
        + ['down'] * 2        # Move insetion point end of the group
        + ['enter']           # Complete move
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Snippet: 'Snippet 3'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 4'
        Snippet: 'Snippet 5'
        Snippet: 'Snippet 7'
        Snippet: 'Snippet 6'
    ''')
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.groups.full_repr()
    assert snapshot_ok


@pytest.mark.asyncio
async def test_move_snippet_between_groups(infile, snapshot_run):
    """A snippet may be moved to a different group."""
    actions = (
        ['down'] * 5          # Move to Snippet 6
        + ['m']               # Start moving
        + ['up'] * 3          # Move insetion point to prev group
        + ['enter']           # Complete move
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Snippet: 'Snippet 6'
        Snippet: 'Snippet 3'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 4'
        Snippet: 'Snippet 5'
        Snippet: 'Snippet 7'
    ''')
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.groups.full_repr()
    assert snapshot_ok


@pytest.mark.asyncio
async def test_move_snippet_to_other_group_start(infile, snapshot_run):
    """A snippet may be moved to the start of a different group."""
    actions = (
        ['down'] * 5          # Move to Snippet 6
        + ['m']               # Start moving
        + ['up'] * 7          # Move insetion top of first group
        + ['enter']           # Complete move
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 6'
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Snippet: 'Snippet 3'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 4'
        Snippet: 'Snippet 5'
        Snippet: 'Snippet 7'
    ''')
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.groups.full_repr()
    assert snapshot_ok


@pytest.mark.asyncio
async def test_move_snippet_to_other_group_end(infile, snapshot_run):
    """A snippet may be moved to the end of a different group."""
    actions = (
        ['down'] * 5          # Move to Snippet 6
        + ['m']               # Start moving
        + ['up'] * 2          # Move insetion point to group end
        + ['enter']           # Complete move
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Snippet: 'Snippet 3'
        Snippet: 'Snippet 6'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 4'
        Snippet: 'Snippet 5'
        Snippet: 'Snippet 7'
    ''')
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.groups.full_repr()
    assert snapshot_ok


@pytest.mark.asyncio
async def test_move_can_empty_a_group(infile_g1, snapshot_run):
    """A snippet move may leave a gruop empty."""
    actions = (
        ['down'] * 2          # Move to Snippet 6
        + ['m']               # Start moving
        + ['enter']           # Complete move
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Snippet: 'Snippet 3'
        Group: Second
        KeywordSet:
        Group: Third
        KeywordSet:
        Snippet: 'Snippet 4'
        Snippet: 'Snippet 5'
    ''')
    runner, snapshot_ok = await snapshot_run(infile_g1, actions)
    assert expect == runner.app.groups.full_repr()
    assert snapshot_ok


@pytest.mark.asyncio
async def test_move_can_insert_in_an_empty_group(infile_g0, snapshot_run):
    """A snippet move may leave a gruop empty."""
    actions = (
        ['down'] * 2          # Move to Snippet 6
        + ['m']               # Start moving
        + ['down'] * 1          # Move insetion point to prev group
        + ['enter']           # Complete move
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 3'
        Group: Third
        KeywordSet:
        Snippet: 'Snippet 4'
        Snippet: 'Snippet 5'
    ''')
    runner, snapshot_ok = await snapshot_run(infile_g0, actions)
    assert expect == runner.app.groups.full_repr()
    assert snapshot_ok


@pytest.mark.asyncio
async def test_insertion_point_is_visisble(infile, snapshot_run, n_moves):
    """The inserrtion point is clearly shown - moving down."""
    actions = (
        ['m']                    # Start moving
        + ['down'] * n_moves     # Move a number of times.
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok


@pytest.mark.asyncio
async def test_insertion_point_is_visisble_top_of_1st_gruop(
        infile, snapshot_run):
    """The inserrtion point is clearly shown - top of first group."""
    actions = (
        ['down']                 # Move to Snippet 2
        + ['m']                  # Start moving
        + ['up']                 # Move up to top of first group.
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok


@pytest.mark.asyncio
async def test_insertion_point_is_visisble_for_empty_group(
        infile_g0, snapshot_run):
    """The inserrtion point is clearly shown for an empty group."""
    actions = (
        ['m']                    # Start moving
        + ['down']  * 2          # Move to the empty group.
    )
    _, snapshot_ok = await snapshot_run(infile_g0, actions)
    assert snapshot_ok
