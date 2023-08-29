"""Clippets tries to be proof against keyboard curious cats."""
from __future__ import annotations
# pylint: disable=redefined-outer-name

import string

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
    Snippet: 'Snippet 6'
    Snippet: 'Snippet 7'
''')
printable = set(string.printable) - set(['\t', '\n', '\x0b', '\x0c', '\r'])
movement = set([
    'left', 'right', 'up', 'down', 'home', 'end', 'insert', 'delete',
    'pageup', 'pagedown'])
special = set([
    '<scroll-up>', '<scroll-down>', '<ignore>', 'ctrl-at', 'space', 'enter',
    'backspace', 'escape', 'shift+escape', 'tab', 'shift-tab'])
fkeys = set('f{n}' for n in range(1, 25))
control = set(f'ctrl+{c}' for c in string.ascii_letters if c not in 'cq')
control |= set(f'ctrl+{c}' for c in string.digits)
control |= set(f'ctrl+shift+{c}' for c in string.digits)
control |= set([
    'ctrl+backslash', 'ctrl+right_square_bracket', 'ctrl+circumflex_accent',
    'ctrl+underscore', 'ctrl+@'])
control |= set(f'ctrl+{m}' for m in movement)
control |= set(f'ctrl+shift++{m}' for m in movement)
control |= set(f'ctrl+{fn}' for fn in fkeys)
shift = set(f'shift+{m}' for m in movement)
all_keys = printable | control  | fkeys | shift

valid_normal_action_keys = set([
    'A', 'a', 'e', 'd', 'f', 'm', 'r', ' ',
    'f1', 'f2', 'f3', 'f7', 'f8', 'f9',
    'up', 'down', 'left', 'right',
    'ctrl+b', 'ctrl+f', 'ctrl+u', 'ctrl+r',
    'space', 'tab', 'shift-tab', 'enter'])
valid_menu_keys = set(['enter', 'tab', 'shift-tab'])
valid_move_keys = set(['up', 'down', 'escape', 'enter'])
valid_help_keys = set(['f1'])


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


@pytest.mark.asyncio
async def test_normal_mode(infile, snapshot_run):
    """Unused keys are ignored when a snippet is selected."""
    actions = sorted(all_keys - valid_normal_action_keys)
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.root.full_repr()
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_normal_mode_group(infile, snapshot_run):
    """Unused keys are ignored when a group is selected."""
    actions = (
        ['left']
        + sorted(all_keys - valid_normal_action_keys)
    )
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.root.full_repr()
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_snippet_menu(infile, snapshot_run):
    """Unused keys are ignored when the snippet menu is active."""
    actions = (
        ['right:snippet-1']
        + sorted(all_keys - valid_menu_keys)
    )
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.root.full_repr()
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_group_menu(infile, snapshot_run):
    """Unused keys are ignored when the group menu is active."""
    actions = (
        ['right:group-1']
        + sorted(all_keys - valid_menu_keys)
    )
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.root.full_repr()
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_move_mode(infile, snapshot_run):
    """Unused keys are ignored when in snippet moving mode."""
    actions = (
        ['m']
        + sorted(all_keys - valid_move_keys)
    )
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.root.full_repr()
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_help_mode(infile, snapshot_run):
    """Unused keys are ignored when showing the help."""
    actions = (
        ['f1']
        + sorted(all_keys - valid_help_keys)
    )
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.root.full_repr()
    assert snapshot_ok, 'Snapshot does not match stored version'
