"""Editing the snippets."""

import pytest
from _pytest.fixtures import FixtureRequest
from syrupy import SnapshotAssertion

from fixtures import check_svg
from support import AppRunner, clean_text, populate


def dump(*strings):
    """Dump one or more blocks of text."""
    print('--------')
    for text in strings:
        for line in text.splitlines(True):
            print(f'  {line!r}')
        print('--------')


@pytest.mark.asyncio
async def test_move_snippet_within_group(snippet_infile,
        snapshot: SnapshotAssertion, request: FixtureRequest):
    """A snippet may be moved within a group."""
    populate(snippet_infile, '''
        Main
          @text@
            Snippet 1
          @text@
            Snippet 2
        Second
          @text@
            Snippet 3
          @text@
            Snippet 4
    ''')
    actions = (
        ['down'] * 3          # Move to Snippet 4
        + ['m']               # Start moving
        + ['up']              # Move insetion point
        + ['enter']           # Complete move
    )
    runner = AppRunner(snippet_infile, actions)
    with runner.logf:
        svg = await runner.run()
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 4'
        Snippet: 'Snippet 3'
    ''')
    assert expect == runner.app.groups.full_repr()
    res = check_svg(snapshot, svg, request, runner.app)
    assert res


@pytest.mark.asyncio
async def test_move_snippet_between_groups(snippet_infile,
        snapshot: SnapshotAssertion, request: FixtureRequest):
    """A snippet may be moved to a different group."""
    populate(snippet_infile, '''
        Main
          @text@
            Snippet 1
          @text@
            Snippet 2
        Second
          @text@
            Snippet 3
          @text@
            Snippet 4
    ''')
    actions = (
        ['down'] * 3          # Move to Snippet 4
        + ['m']               # Start moving
        + ['up'] * 2          # Move insetion point to prev group
        + ['enter']           # Complete move
    )
    runner = AppRunner(snippet_infile, actions)
    svg = await runner.run()
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Snippet: 'Snippet 4'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 3'
    ''')
    assert expect == runner.app.groups.full_repr()
    res = check_svg(snapshot, svg, request, runner.app)
    assert res
