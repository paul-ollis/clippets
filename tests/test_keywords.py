"""Keywords are highlighted within snippet text.

Keywords are useful to make help spot relevant snippets within a group.
"""
from __future__ import annotations
# pylint: disable=redefined-outer-name

import functools

import pytest

from support import clean_text, populate

std_infile_text = '''
    Main
      @keywords@
        {keywords}
      @text@
        Keywords are used to make it easier for the user to find the correct
        snippet.
      @md@
        Keywords are highlighted even within *Markdown text*.

        - The keyword **highlighting** is in addition to the Mardkown
          highlighting.
        - Keywords, quite correctly only matches complete words.
      @md@
        The third snippet.
    Second
      @keywords@
        {g2_keywords}
      @text@
        Keywords are associated with a group, giving the user fine grained
        control.
'''


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    def pop(kwstr: str, g2_kwstr: str = 'fine'):
        """Populate the input file after insrting the keyword set."""
        text = std_infile_text.format(keywords=kwstr, g2_keywords=g2_kwstr)
        populate(snippet_infile, text)
        return snippet_infile

    return pop


@pytest.mark.asyncio
async def test_keywords_highlight_in_plaintext_snippets(
        infile, snapshot_run_dyn):
    """Plain text snippets show keyword highlighting.

    Note that keywords are group specific.
    """
    actions = ()
    kw = 'user'
    _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
    assert snapshot_ok


@pytest.mark.asyncio
async def test_keywords_highlight_in_md_snippets(infile, snapshot_run_dyn):
    """Marddown text snippets show keyword highlighting."""
    actions = ()
    kw = 'even only'
    _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
    assert snapshot_ok


@pytest.mark.asyncio
async def test_keywords_work_only_on_whole_words(infile, snapshot_run_dyn):
    """Only whoe wordsa are highlighted."""
    actions = ()
    kw = 'correct word'
    _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
    assert snapshot_ok


@pytest.mark.asyncio
async def test_keywords_augment_md_highlighting(infile, snapshot_run_dyn):
    """Keyword highlighting adds to existing markdown highlighting.

    For example, a bold keyword reamins bold, but is also coloured.
    """
    actions = ()
    kw = 'highlighting text'
    _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
    assert snapshot_ok


@pytest.mark.asyncio
async def test_keywords_can_be_edited(
        infile, snapshot_run_dyn, edit_text_file):
    """Keyword highlighting adds to existing markdown highlighting.

    For example, a bold keyword reamins bold, but is also coloured.
    """
    populate(edit_text_file, 'Markdown\ntext\n')
    actions = (
        ['f7']                # Edit the first group's keywords.
    )
    kw = 'highlighting text'
    _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
    assert 'highlighting\ntext' == edit_text_file.prev_text
    assert snapshot_ok


@pytest.mark.asyncio
async def test_keywords_cannot_be_edited_if_no_snippet_selected(
        infile, snapshot_run_dyn, edit_text_file):
    """If no snippet is showns as selected, keywords cannot be edited."""
    populate(edit_text_file, 'Markdown\ntext\n')
    actions = (
        ['f9']                  # Close all groups.
        + ['f7']                # Edit the first group's keywords.
    )
    kw = 'highlighting text'
    _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
    assert not edit_text_file.has_run
    assert snapshot_ok
