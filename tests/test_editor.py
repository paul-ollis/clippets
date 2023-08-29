"""Clippets provides a built-in editor.

The editor provides many of the typical editor features, but does not try to
be too powerful.
"""
from __future__ import annotations
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use

import os

import pytest

from support import populate

std_infile_text = '''
    Main
      @md@
        Keywords are highlighted even within *Markdown text*.

        - The keyword **highlighting** is in addition to the Markdown
          highlighting.
        - Keywords, quite correctly only matches complete words.
'''

@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


@pytest.fixture
def long_infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    text = std_infile_text + '\n'
    text += '\n'.join(f'        Line {i + 1}' for i in range(60))
    populate(snippet_infile, text)
    return snippet_infile


@pytest.fixture(autouse=True)
def set_env():
    """Set up the environment for these tests."""
    os.environ['CLIPPETS_EDITOR'] = ''


@pytest.mark.asyncio
async def test_mouse_can_place_the_cursor(infile, snapshot_run):
    """Left clicking with the mouse moves the cursor.."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['left:editor_win+5x2']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_mouse_can_make_selection(infile, snapshot_run):
    """Dragging with mouse selects text."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['leftdown:editor_win+5x2']
        + ['drag_release:editor_win+20x3']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_can_copy_and_paste(infile, snapshot_run):
    """Basic copy-and-paste is provided."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['down'] * 2
        + ['shift+down']
        + ['ctrl+c']
        + ['down']
        + ['ctrl+v']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_can_cut_and_paste(infile, snapshot_run):
    """Basic cut-and-paste is provided."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['down'] * 2
        + ['shift+down']
        + ['ctrl+x']
        + ['down']
        + ['ctrl+v']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_printable_key_replace_selection(infile, snapshot_run):
    """A printable key deletes and replaces any current selection."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['shift+right'] * 5
        + ['x']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_paste_replace_selection(infile, snapshot_run):
    """Pasting text replaces the current selection."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['shift+right'] * 7
        + ['ctrl+c']
        + ['down'] * 2
        + ['right'] * 2
        + ['shift+right'] * 3
        + ['ctrl+v']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_ctrl_a_selects_everything(infile, snapshot_run):
    """The ctrl+a key combination selects all the text."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['down'] * 2
        + ['ctrl+a']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_page_down_key_is_handled(long_infile, snapshot_run):
    """The page down key scrolls appropriately."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['pagedown'] * 3
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(long_infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_page_up_key_is_handled(long_infile, snapshot_run):
    """The page up key scrolls appropriately."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['pagedown'] * 3
        + ['pageup']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(long_infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_right_arrow_key_scrolls_appropriately(
        infile, snapshot_run):
    """The right arrow key scrolls horizontally if necessary."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['down'] * 2
        + ['backspace'] * 2
        + ['right'] * 20
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_left_arrow_key_scrolls_appropriately(
        infile, snapshot_run):
    """The left arrow key scrolls horizontally if necessary."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['down'] * 2
        + ['backspace'] * 2
        + ['right'] * 20
        + ['pause:0.1']
        + ['left'] * 55
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_ctrl_home_moves_cursor_to_start_of_buffer(
        long_infile, snapshot_run):
    """Pressing ctrl+home moves to the start of the buffer."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['pagedown'] * 3
        + ['ctrl+home']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(long_infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_ctrl_end_moves_cursor_to_end_of_buffer(
        long_infile, snapshot_run):
    """Pressing ctrl+end moves to the end of the buffer."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['ctrl+end']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(long_infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_arrow_keys_move_the_cursor(
        infile, snapshot_run):
    """The arrow keys move the cursor in typical fashion."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['down'] * 4
        + ['right'] * 2
        + ['ctrl+right']
        + ['up'] * 2
        + ['ctrl+left']
        + ['left']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_ctrl_right_key_moves_word_wise(
        infile, snapshot_run):
    """The ctrl+right key moves the cursor in word-wise fashion."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['ctrl+right'] * 10
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_ctrl_right_stops_end_end_of_last_line(
        infile, snapshot_run):
    """The ctrl+right does not try to move past end of buffer."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['down'] * 4
        + ['ctrl+right'] * 10
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_ctrl_left_key_moves_word_wise(
        infile, snapshot_run):
    """The ctrl+left key moves the cursor in word-wise fashion."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['down'] * 3
        + ['ctrl+left'] * 12
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_ctrl_left_stops_at_start_of_first_line(
        infile, snapshot_run):
    """The ctrl+left does not try to move past start of buffer."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['right'] * 11
        + ['ctrl+left'] * 5
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_right_arrow_wraps(
        infile, snapshot_run):
    """The right arrow key wraps when it reaches the end of the line."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['end']
        + ['right']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_right_arrow_stops_at_end_of_last_line(
        infile, snapshot_run):
    """The right arrow stops at the end of the last line."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['down'] * 4
        + ['end']
        + ['right']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_left_arrow_wraps(
        infile, snapshot_run):
    """The left arrow key wraps when it reaches the start of the line."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['down']
        + ['left']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_left_arrow_stops_at_start_of_first_line(
        infile, snapshot_run):
    """The left arrow stops at the start of the first line."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_up_arrow_stops_at_start_of_buffer(
        infile, snapshot_run):
    """The up arrow stops at the start of the buffer."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['right'] * 5
        + ['up']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_down_arrow_stops_at_end_of_buffer(
        infile, snapshot_run):
    """The down arrow stops at the end of the buffer."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['down'] * 4
        + ['right'] * 5
        + ['down'] * 5
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_enter_starts_new_line(
        infile, snapshot_run):
    """The enter key starts a new line, when pressed on a blank line."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['down']
        + ['enter']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_enter_splits_a_line(
        infile, snapshot_run):
    """The enter key splits when pressed within a line."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['right'] * 5
        + ['enter']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_enter_keeps_indent(
        infile, snapshot_run):
    """The enter key splits keeps the indent of the previous line."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['home']
        + ['down'] * 3
        + ['end']
        + ['enter']
        + list('New text')
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_tab_key_inserts_4_spaces(infile, snapshot_run):
    """The Tab key simply inserts 4 spaces."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['right']
        + ['tab']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_backspace_deletes_previous_character(infile, snapshot_run):
    """The backspace key deletes the previous character, if possible."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['right'] * 2
        + ['backspace'] * 3
        + ['down']
        + ['backspace']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_backspace_deletes_the_selection(infile, snapshot_run):
    """The backspace deletes the selection, if present."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['shift+right'] * 5
        + ['backspace']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_del_deletes_previous_character(infile, snapshot_run):
    """The delete key deletes the next character, if possible."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['right'] * 2
        + ['delete'] * 3
        + ['down'] * 4
        + ['end']
        + ['delete']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_del_deletes_the_selection(infile, snapshot_run):
    """The delete deletes the selection, if present."""
    actions = (
        ['e']                              # Edit the first snippet
        + ['shift+right'] * 5
        + ['delete']
        + ['snapshot:']
        + ['ctrl+q']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'
