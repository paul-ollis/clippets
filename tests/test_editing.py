"""Editing the snippets."""
from __future__ import annotations
# pylint: disable=redefined-outer-name

import os
from pathlib import Path

import pytest

from support import clean_text, populate

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


# TODO: Move to conftest. This is duplicated.
@pytest.fixture(autouse=True)
def set_env():
    """Set up the environment for these tests."""
    os.environ['CLIPPETS_EDITOR'] = f'python {HERE / "edit_helper.py"}'


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


class TestKeyboardControlled:
    """Using the keyboard as much as possible."""

    @pytest.mark.asyncio
    async def test_a_snippet_can_be_edited(
            self, infile, edit_text_file, snapshot_run):
        """A snippet's contents may be edited."""
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['down']              # Move to Snippet 2
            + ['e']               # Edit it
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            Snippet: 'Snippet 1'
            Snippet: 'Snippet 2 - edited'
            MarkdownSnippet: 'Snippet 3'
        ''')
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert expect == runner.app.groups.full_repr()
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_a_snippet_can_be_duplicated(
            self, infile, edit_text_file, snapshot_run):
        """A snippet's contents may be duplicated and immediately edited."""
        populate(edit_text_file, 'Snippet 4')
        actions = (
            ['down'] * 2          # Move to Snippet 3
            + ['d']               # Duplicate and edit it
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            Snippet: 'Snippet 1'
            Snippet: 'Snippet 2'
            MarkdownSnippet: 'Snippet 3'
            MarkdownSnippet: 'Snippet 4'
        ''')
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert expect == runner.app.groups.full_repr()
        assert 'Snippet 3' == edit_text_file.prev_text
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_clipboard_can_be_edited(
            self, infile, edit_text_file, snapshot_run):
        """The prepared clipboard content can be edited."""
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['down']              # Move to Snippet 2
            + ['enter']           # Add to the clipboard
            + ['f2']              # Edit the clipboard preview
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_clipboard_edit_can_be_undone(
            self, infile, edit_text_file, snapshot_run):
        """Edits to the clipboard can be undone."""
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['down']              # Move to Snippet 2
            + ['enter']           # Add to the clipboard
            + ['f2']              # Edit the clipboard preview
            + ['ctrl+u']          # Undo the edit.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_clipboard_edit_undo_can_be_redone(
            self, infile, edit_text_file, snapshot_run):
        """The Ctrl+R key implement re-do."""
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['down']              # Move to Snippet 2
            + ['enter']           # Add to the clipboard
            + ['f2']              # Edit the clipboard preview
            + ['ctrl+u']          # Undo the edit.
            + ['ctrl+r']          # The redo it again
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_clipboard_edit_can_restored_by_undo_after_new_add(
            self, infile, edit_text_file, snapshot_run):
        """The undo function is multi-level to protect clipboard edits.

        Adding a snippet after clipboard editing will lose the manual edits,
        but undoing will restore the edit.
        """
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['down']              # Move to Snippet 2
            + ['enter']           # Add to the clipboard
            + ['f2']              # Edit the clipboard preview
            + ['down']            # Move to Snippet 3
            + ['enter']           # Add to the clipboard, loses edit.
            + ['ctrl+u']          # Undo the add.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_up_to_9_backups_are_made(
            self, infile, edit_text_file, snapshot_run):
        """Up to 9 backup files are maintained when the file is saved."""
        def update_text():
            populate(edit_text_file, next(data))

        data = (f'Snippet {n}' for n in range(4, 14))
        populate(edit_text_file, next(data))
        actions = (
            ['down'] * 2                       # Move to Snippet 3
            + ['d']                            # Duplicate

            + [update_text]                    # Change edit emulation text.
            + ['d']                            # Duplicate the new snippet
            + [update_text, 'd'] * 8           # ... and so on.
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            Snippet: 'Snippet 1'
            Snippet: 'Snippet 2'
            MarkdownSnippet: 'Snippet 3'
            MarkdownSnippet: 'Snippet 4'
            MarkdownSnippet: 'Snippet 5'
            MarkdownSnippet: 'Snippet 6'
            MarkdownSnippet: 'Snippet 7'
            MarkdownSnippet: 'Snippet 8'
            MarkdownSnippet: 'Snippet 9'
            MarkdownSnippet: 'Snippet 10'
            MarkdownSnippet: 'Snippet 11'
            MarkdownSnippet: 'Snippet 12'
            MarkdownSnippet: 'Snippet 13'
        ''')
        runner, snapshot_ok = await snapshot_run(
            infile, actions, post_delay=0.2)
        assert 9 == len(infile.backup_paths())
        assert expect == runner.app.groups.full_repr()
        assert 'Snippet 12' == edit_text_file.prev_text
        assert snapshot_ok


class TestMouseControlled:
    """Generally preferring to use the mouse."""

    @pytest.mark.asyncio
    async def test_a_snippet_can_be_edited(
            self, infile, edit_text_file, snapshot_run):
        """A snippet's contents may be edited."""
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['right:snippet-1']       # Open snippet-2 menu.
            + ['left:edit']           # Select edit.
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            Snippet: 'Snippet 1'
            Snippet: 'Snippet 2 - edited'
            MarkdownSnippet: 'Snippet 3'
        ''')
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert expect == runner.app.groups.full_repr()
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_a_snippet_can_be_duplicated(
            self, infile, edit_text_file, snapshot_run):
        """A snippet's contents may be duplicated and immediately edited."""
        populate(edit_text_file, 'Snippet 4')
        actions = (
            ['right:snippet-2']       # Open snippet-3 menu.
            + ['left:duplicate']      # Select edit.
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            Snippet: 'Snippet 1'
            Snippet: 'Snippet 2'
            MarkdownSnippet: 'Snippet 3'
            MarkdownSnippet: 'Snippet 4'
        ''')
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert expect == runner.app.groups.full_repr()
        assert 'Snippet 3' == edit_text_file.prev_text
        assert snapshot_ok
