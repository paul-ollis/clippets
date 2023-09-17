"""Keywords are highlighted within snippet text.

Keywords are useful to make help spot relevant snippets within a group.
"""
from __future__ import annotations
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use

import os

import pytest

from support import populate

std_infile_text = '''
    Main
      @keywords@
        {keywords}
      @text@
        Keywords are used to make it easier for the user to find the correct
        snippet.
      @md@
        Keywords are highlighted even within *Markdown text*.

        - The keyword **highlighting** is in addition to the Markdown
          highlighting.
        - Keywords, quite correctly, only match complete words.
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
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_keywords_highlight_in_md_snippets(infile, snapshot_run_dyn):
    """Marddown text snippets show keyword highlighting."""
    actions = ()
    kw = 'even only'
    _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_keywords_work_only_on_whole_words(infile, snapshot_run_dyn):
    """Only whoe wordsa are highlighted."""
    actions = ()
    kw = 'correct word'
    _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_keywords_augment_md_highlighting(infile, snapshot_run_dyn):
    """Keyword highlighting adds to existing markdown highlighting.

    For example, a bold keyword reamins bold, but is also coloured.
    """
    actions = ()
    kw = 'highlighting text'
    _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_keywords_can_be_edited(
        infile, snapshot_run_dyn, edit_text_file):
    """Keyword highlighting adds to existing markdown highlighting.

    For example, a bold keyword reamins bold, but is also coloured.
    """
    populate(edit_text_file, 'Markdown\ntext\n')
    actions = (
        ['f7']                # Edit the first group's keywords.
        + ['wait:1.0:EditorHasExited']
    )
    kw = 'highlighting text'
    _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
    assert 'highlighting\ntext' == edit_text_file.prev_text
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_ui_is_greyed_out_during_clipboard_editing(
        infile, snapshot_run, edit_text_file):
    """The main TUI is greyed out during editing of keywords."""
    populate(edit_text_file, 'XMarkdown\ntext\n')
    actions = (
        ['f7']                # Edit the first group's keywords.
        + ['snapshot:']         # Take snapshot with editor running
        + ['end_edit:']         # Stop the editor.
        + ['wait:1.0:EditorHasExited']
    )
    kw = 'highlighting text'
    _, snapshot_ok = await snapshot_run(
        infile(kw), actions, control_editor=True)
    assert 'highlighting\ntext' == edit_text_file.prev_text
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_select_group_used_if_no_snippets(
        infile, snapshot_run_dyn, edit_text_file):
    """If no snippet is showns as selected, the slected gruop is used."""
    populate(edit_text_file, 'Markdown\ntext\n')
    actions = (
        ['f9']                  # Close all groups.
        + ['f7']                # Edit the first group's keywords.
        + ['wait:1.0:EditorHasExited']
        + ['f9']                # Open all groups.
    )
    kw = 'highlighting text'
    _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
    assert 'highlighting\ntext' == edit_text_file.prev_text
    assert snapshot_ok, 'Snapshot does not match stored version'


class TestInternalEditor:
    """Using the built-in editor."""

    @pytest.fixture(autouse=True)
    @classmethod
    def set_env(cls):
        """Set up the environment for these tests."""
        os.environ['CLIPPETS_EDITOR'] = ''

    @pytest.mark.asyncio
    async def test_keywords_can_be__edited(
            self, infile, snapshot_run_dyn):
        """The internal editor can be used to edit the keywords."""
        actions = (
            ['f7']                # Edit the first group's keywords.
            + ['home']
            + ['shift-end']
            + ['del']
            + list('Markdown')
            + ['enter']
            + list('text')
            + ['ctrl+s']
        )
        kw = 'highlighting text'
        _, snapshot_ok = await snapshot_run_dyn(infile(kw), actions)
        assert snapshot_ok, 'Snapshot does not match stored version'
