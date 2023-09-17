"""Monitoring and reloading of the input file."""
from __future__ import annotations
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use

from pathlib import Path

import pytest

from support import clean_text, long_infile_text, populate

HERE = Path(__file__).parent
std_infile_text = '''
    Main
      @text@
        Snippet 1
      @text@
        Snippet 2
      @md@
        Snippet 3
'''
multi_group_infile = '''
    Main
      @text@
        Snippet 1
    Second
      @text@
        Snippet 2
    Third
      @md@
        Snippet 3
'''

# TODO: These tests rely on the OS/filesystem combination providing
#       modification timestamps accurato to better than 0.01 seconds.


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


@pytest.mark.asyncio
async def test_change_to_the_file_is_detected(infile, snapshot_run):
    """A change to the input file is detected and a popup menu presented."""
    def update_file():
        text = std_infile_text.replace('Snippet 1', 'Snippet 1 - modified')
        populate(infile, text)

    actions = (
        [update_file]
        + ['pause: 0.2']
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_change_to_the_file_can_be_loadd(infile, snapshot_run):
    """The updated file can be loaded."""
    def update_file():
        text = std_infile_text.replace('Snippet 1', 'Snippet 1 - modified')
        populate(infile, text)

    actions = (
        ['pause: 0.01']
        + [update_file]
        + ['pause:0.22']
        + ['enter']
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1 - modified'
        Snippet: 'Snippet 2'
        MarkdownSnippet: 'Snippet 3'
    ''')
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.root.full_repr()
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_change_to_the_file_can_be_ignored(infile, snapshot_run):
    """The updated file can be be ignored."""
    def update_file():
        text = std_infile_text.replace('Snippet 1', 'Snippet 1 - modified')
        populate(infile, text)

    actions = (
        ['pause: 0.01']
        + [update_file]
        + ['pause:0.22']
        + ['tab']
        + ['enter']
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        MarkdownSnippet: 'Snippet 3'
    ''')
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.root.full_repr()
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_folded_groups_fold_may_be_maintained(infile, snapshot_run):
    """Clippets tries to retain the folded group state after a reload."""
    def update_file():
        text = clean_text(multi_group_infile).replace(
            'Snippet 2', 'Snippet 2\n  @text@\n    Snippet 2A')
        populate(infile, text)

    actions = (
        ['left:group-2']
        + ['pause: 0.01']
        + [update_file]
        + ['pause:0.22']
        + ['enter']
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 2'
        Snippet: 'Snippet 2A'
        Group: Third
        KeywordSet:
        MarkdownSnippet: 'Snippet 3'
    ''')
    populate(infile, multi_group_infile)
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.root.full_repr()
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_selection_is_adjusted_if_necessary(infile, snapshot_run):
    """If necessary the selected snippet is adjusted."""
    def update_file():
        text = clean_text(std_infile_text).replace(
            '  @md@\n    Snippet 3', '')
        populate(infile, text)

    actions = (
        ['down'] * 2
        + ['pause: 0.01']
        + [update_file]
        + ['pause:0.22']
        + ['enter']
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
    ''')
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.root.full_repr()
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_display_scrolls_if_necessary(infile, snapshot_run):
    """If necessary the display scrolls when theselection is adjusted."""
    def update_file():
        text = clean_text(long_infile_text).replace(
            '  @text@\n    Snippet 14', '')
        populate(infile, text)

    actions = (
        ['down'] * 13
        + ['pause: 0.01']
        + [update_file]
        + ['pause:0.22']
        + ['enter']
    )
    populate(infile, long_infile_text)
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_zero_snippets_is_handled(infile, snapshot_run):
    """If the modified file has no snippets, nothing bad happens."""
    def update_file():
        populate(infile, '''Main''')

    actions = (
        ['pause: 0.01']
        + [update_file]
        + ['pause:0.22']
        + ['enter']
    )
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
    ''')
    runner, snapshot_ok = await snapshot_run(infile, actions)
    assert expect == runner.app.root.full_repr()
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_deletion_of_the_file_is_hnandled(infile, snapshot_run):
    """If the file is deleted, nothing bad happens."""
    def remove_file():
        infile.delete()

    actions = (
        ['pause: 0.01']
        + [remove_file]
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'
