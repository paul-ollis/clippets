"""Editing the snippets."""
from __future__ import annotations
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use

import os
from pathlib import Path

import pytest

from support import clean_text, populate

HERE = Path(__file__).parent
std_infile_text = '''
    @title: User supplied title
    Main
      @text@
        Snippet 1
      @text@
        Snippet 2
      @md@
        Snippet 3
'''
empty_group_infile_text = '''
    @title: User supplied title
    Main
'''
two_group_infile_text = '''
    @title: User supplied title
    Main
      @text@
        Snippet 1
      @text@
        Snippet 2
      @md@
        Snippet 3
    Third
      @md@
        Snippet 4
'''


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


@pytest.fixture
def empty_group_infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, empty_group_infile_text)
    return snippet_infile


@pytest.fixture
def two_group_infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, two_group_infile_text)
    return snippet_infile


class TestKeyboardControlled:
    """Using the keyboard as much as possible."""

    @pytest.mark.asyncio
    async def test_a_snippet_can_be_edited(
            self, infile, edit_text_file, snapshot_run):
        """A snippet's contents may be edited."""
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['down']                         # Move to Snippet 2
            + ['e']                          # Edit it
            + ['wait:0.5:EditorHasExited']
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
        assert expect == runner.app.root.full_repr()
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_snippet_can_be_duplicated(
            self, infile, edit_text_file, snapshot_run):
        """A snippet's contents may be duplicated and immediately edited."""
        populate(edit_text_file, 'Snippet 4')
        actions = (
            ['down'] * 2          # Move to Snippet 3
            + ['d']               # Duplicate and edit it
            + ['wait:0.5:EditorHasExited']
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
        assert expect == runner.app.root.full_repr()
        assert 'Snippet 3' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_editing_maintains_folded_state(
            self, two_group_infile, edit_text_file, snapshot_run):
        """Folded groups remain folded after editing."""
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['left']                         # Move to first group.
            + ['down']                       # ... then next group.
            + ['f']                          # ... then fold.
            + ['up']                         # ... back to first group.
            + ['right']                      # ... then snippet.
            + ['down']                       # ... then second snippet.
            + ['e']                          # Edit it
            + ['wait:0.5:EditorHasExited']
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            Snippet: 'Snippet 1'
            Snippet: 'Snippet 2 - edited'
            MarkdownSnippet: 'Snippet 3'
            Group: Third
            KeywordSet:
            MarkdownSnippet: 'Snippet 4'
        ''')
        runner, snapshot_ok = await snapshot_run(two_group_infile, actions)
        assert expect == runner.app.root.full_repr()
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_edit_dup_etc_ignored_for_group(
            self, infile, edit_text_file, snapshot_run):
        """Request to edit, etc. are ignored when a group is selected."""
        populate(edit_text_file, 'Snippet 4')
        actions = (
            ['left']              # Delect the group.
            + ['e']               # Try to edit.
            + ['d']               # Try to duplicate.
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
    async def test_a_new_snippet_can_be_added_after_a_snippet(
            self, infile, edit_text_file, snapshot_run):
        """A snippet may be added after another."""
        populate(edit_text_file, 'New snippet')
        actions = (
            ['down'] * 2          # Move to Snippet 3.
            + ['a']               # Add a new snippet.
            + ['wait:0.5:EditorHasExited']
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            Snippet: 'Snippet 1'
            Snippet: 'Snippet 2'
            MarkdownSnippet: 'Snippet 3'
            MarkdownSnippet: 'New snippet'
        ''')
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert expect == runner.app.root.full_repr()
        assert '' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_new_snippet_can_be_added_at_group_start(
            self, infile, edit_text_file, snapshot_run):
        """A snippet may be added at the start of a group."""
        populate(edit_text_file, 'New snippet')
        actions = (
            ['left']              # Select the group.
            + ['a']               # Add a new snippet.
            + ['wait:0.5:EditorHasExited']
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            MarkdownSnippet: 'New snippet'
            Snippet: 'Snippet 1'
            Snippet: 'Snippet 2'
            MarkdownSnippet: 'Snippet 3'
        ''')
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert expect == runner.app.root.full_repr()
        assert '' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_new_snippet_can_be_added_to_an_empty_group(
            self, empty_group_infile, edit_text_file, snapshot_run):
        """A snippet may be added to an empty group."""
        populate(edit_text_file, 'New snippet')
        actions = (
            ['a']               # Add a new snippet.
            + ['wait:0.5:EditorHasExited']
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            MarkdownSnippet: 'New snippet'
        ''')
        runner, snapshot_ok = await snapshot_run(empty_group_infile, actions)
        assert expect == runner.app.root.full_repr()
        assert '' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_new_group_can_be_added(
            self, two_group_infile, snapshot_run):
        """A new group may be added after another."""
        actions = (
            ['left']              # Move to group.
            + ['A']               # Add a new group.
            + list('Second')
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
            Group: Second
            KeywordSet:
            Group: Third
            KeywordSet:
            MarkdownSnippet: 'Snippet 4'
        ''')
        runner, snapshot_ok = await snapshot_run(two_group_infile, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_snippet_can_be_moved_into_new_group(
            self, two_group_infile, snapshot_run):
        """A snippet may be moved into a newly created group."""
        actions = (
            ['left']              # Move to group.
            + ['A']               # Add a new group.
            + list('Second')
            + ['tab']
            + ['enter']
            + ['up']              # Move to first group.
            + ['right']           # Move to first snippet.
            + ['m']               # Move snippet...
            + ['down'] * 2        # ... to new group.
            + ['enter']
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            Snippet: 'Snippet 2'
            MarkdownSnippet: 'Snippet 3'
            Group: Second
            KeywordSet:
            Snippet: 'Snippet 1'
            Group: Third
            KeywordSet:
            MarkdownSnippet: 'Snippet 4'
        ''')
        runner, snapshot_ok = await snapshot_run(two_group_infile, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_new_group_can_be_added_at_end(
            self, two_group_infile, snapshot_run):
        """A new group may be added as the last group."""
        actions = (
            ['left']              # Move to group.
            + ['down']            # Move to bottom group.
            + ['A']               # Add a new group.
            + list('Second')
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
            Group: Third
            KeywordSet:
            MarkdownSnippet: 'Snippet 4'
            Group: Second
            KeywordSet:
        ''')
        runner, snapshot_ok = await snapshot_run(two_group_infile, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_new_group_can_be_renamed(
            self, two_group_infile, snapshot_run):
        """An existing group may be renamed."""
        actions = (
            ['left']              # Move to group.
            + ['down']            # Move to bottom group.
            + ['r']               # Choose to rename the group.
            + ['backspace'] * 5
            + list('Second')
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
            Group: Second
            KeywordSet:
            MarkdownSnippet: 'Snippet 4'
        ''')
        runner, snapshot_ok = await snapshot_run(two_group_infile, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_duplicate_group_cannot_be_added(
            self, two_group_infile, snapshot_run):
        """The user is prevented from adding a group with a duplicate name."""
        actions = (
            ['left']              # Move to group.
            + ['A']               # Add a new group.
            + list('Third')
        )
        _, snapshot_ok = await snapshot_run(two_group_infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_clipboard_can_be_edited(
            self, infile, edit_text_file, snapshot_run):
        """The prepared clipboard content can be edited."""
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['down']              # Move to Snippet 2
            + ['enter']           # Add to the clipboard
            + ['f2']              # Edit the clipboard preview
            + ['wait:0.5:EditorHasExited']
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_clipboard_edit_can_be_undone(
            self, infile, edit_text_file, snapshot_run):
        """Edits to the clipboard can be undone."""
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['down']              # Move to Snippet 2
            + ['enter']           # Add to the clipboard
            + ['f2']              # Edit the clipboard preview
            + ['wait:0.5:EditorHasExited']
            + ['ctrl+u']          # Undo the edit.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_clipboard_edit_undo_can_be_redone(
            self, infile, edit_text_file, snapshot_run):
        """The Ctrl+R key implement re-do."""
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['down']              # Move to Snippet 2
            + ['enter']           # Add to the clipboard
            + ['f2']              # Edit the clipboard preview
            + ['wait:0.5:EditorHasExited']
            + ['ctrl+u']          # Undo the edit.
            + ['ctrl+r']          # The redo it again
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

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
            + ['wait:0.5:EditorHasExited']
            + ['down']            # Move to Snippet 3
            + ['enter']           # Add to the clipboard, loses edit.
            + ['ctrl+u']          # Undo the add.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_up_to_10_backups_are_made(
            self, infile, edit_text_file, snapshot_run):
        """Up to 10 backup files are maintained when the file is saved."""
        def update_text():
            populate(edit_text_file, next(data))

        data = (f'Snippet {n}' for n in range(4, 15))
        populate(edit_text_file, next(data))
        actions = (
            ['down'] * 2                      # Move to Snippet 3
            + ['d']                           # Duplicate
            + ['wait:1.0:EditorHasExited']
            + [update_text]                   # Change edit emulation text.
            + ['d']                           # Duplicate the new snippet
            + ['wait:1.0:EditorHasExited']
            + [update_text, 'd',
               'wait:1.0:EditorHasExited'] * 9  # ... and so on.
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
            MarkdownSnippet: 'Snippet 14'
        ''')
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert 10 == len(infile.backup_paths())                 # noqa: PLR2004
        assert expect == runner.app.root.full_repr()
        assert 'Snippet 13' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_ui_is_greyed_out_during_snippet_editing(
            self, infile, edit_text_file, snapshot_run):
        """The main TUI is greayed out during editing."""
        populate(edit_text_file, 'Snippet 2')
        actions = (
            ['down']                # Move to Snippet 2
            + ['e']                 # Edit it
            + ['snapshot:']         # Take snapshot with editor running
            + ['end_edit:']         # Stop the editor.
            + ['wait:0.5:EditorHasExited']
        )
        _, snapshot_ok = await snapshot_run(
            infile, actions, control_editor=True)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_ui_is_greyed_out_during_snippet_duplication(
            self, infile, edit_text_file, snapshot_run):
        """The main TUI is greayed out during editing a duplicated snippet."""
        populate(edit_text_file, 'Snippet 2')
        actions = (
            ['down']                # Move to Snippet 2
            + ['d']                 # Edit it
            + ['snapshot:']         # Take snapshot with editor running
            + ['end_edit:']         # Stop the editor.
            + ['wait:0.5:EditorHasExited']
        )
        _, snapshot_ok = await snapshot_run(
            infile, actions, control_editor=True)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_ui_is_greyed_out_during_clipboard_editing(
            self, infile, edit_text_file, snapshot_run):
        """The main TUI is greayed out during editing of the clipboard."""
        populate(edit_text_file, 'Snippet 2')
        actions = (
            ['down']                # Move to Snippet 2
            + ['f2']                # Edit clipboard
            + ['snapshot:']         # Take snapshot with editor running
            + ['end_edit:']         # Stop the editor.
            + ['wait:0.5:EditorHasExited']
        )
        _, snapshot_ok = await snapshot_run(
            infile, actions, control_editor=True)
        assert snapshot_ok, 'Snapshot does not match stored version'


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
            + ['wait:0.5:EditorHasExited']
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
        assert expect == runner.app.root.full_repr()
        assert 'Snippet 2' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_snippet_can_be_duplicated(
            self, infile, edit_text_file, snapshot_run):
        """A snippet's contents may be duplicated and immediately edited."""
        populate(edit_text_file, 'Snippet 4')
        actions = (
            ['right:snippet-2']       # Open snippet-3 menu.
            + ['left:duplicate']      # Select edit.
            + ['wait:0.5:EditorHasExited']
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
        assert expect == runner.app.root.full_repr()
        assert 'Snippet 3' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_new_snippet_can_be_added_after_a_snippet(
            self, infile, edit_text_file, snapshot_run):
        """A snippet may be added after another."""
        populate(edit_text_file, 'New snippet')
        actions = (
            ['right:snippet-2']       # Open snippet-3 menu.
            + ['left:add_snippet']            # Select edit.
            + ['wait:0.5:EditorHasExited']
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            Snippet: 'Snippet 1'
            Snippet: 'Snippet 2'
            MarkdownSnippet: 'Snippet 3'
            MarkdownSnippet: 'New snippet'
        ''')
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert expect == runner.app.root.full_repr()
        assert '' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_new_snippet_can_be_added_at_group_start(
            self, infile, edit_text_file, snapshot_run):
        """A snippet may be added at the start of a group."""
        populate(edit_text_file, 'New snippet')
        actions = (
            ['right:group-1']         # Open group-1 menu.
            + ['left:add_snippet']            # Select edit.
            + ['wait:0.5:EditorHasExited']
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            MarkdownSnippet: 'New snippet'
            Snippet: 'Snippet 1'
            Snippet: 'Snippet 2'
            MarkdownSnippet: 'Snippet 3'
        ''')
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert expect == runner.app.root.full_repr()
        assert '' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_new_group_can_be_added(
            self, two_group_infile, snapshot_run):
        """A new group may be added after another group."""
        actions = (
            ['right:group-1']         # Open group-1 menu.
            + ['left:add_group']      # Select add group.
            + list('Second')
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
            Group: Second
            KeywordSet:
            Group: Third
            KeywordSet:
            MarkdownSnippet: 'Snippet 4'
        ''')
        runner, snapshot_ok = await snapshot_run(two_group_infile, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_new_group_can_be_renamed(
            self, two_group_infile, snapshot_run):
        """An existing group may be renamed."""
        actions = (
            ['right:group-2']         # Open group-1 menu.
            + ['left:rename_group']   # Select add group.
            + ['backspace'] * 5
            + list('Second')
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
            Group: Second
            KeywordSet:
            MarkdownSnippet: 'Snippet 4'
        ''')
        runner, snapshot_ok = await snapshot_run(two_group_infile, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_group_rename_allows_original_name(
            self, two_group_infile, snapshot_run):
        """The esiting name is permittedwhen renaming a group."""
        actions = (
            ['right:group-2']         # Open group-1 menu.
            + ['left:rename_group']   # Select add group.
            + ['backspace'] * 5
            + list('Third')
        )
        _, snapshot_ok = await snapshot_run(two_group_infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'


class TestInternalEditor:
    """Using the built-in editor."""

    @pytest.fixture(autouse=True)
    @classmethod
    def set_env(cls):
        """Set up the environment for these tests."""
        os.environ['CLIPPETS_EDITOR'] = ''

    @pytest.mark.asyncio
    async def test_a_snippet_can_be_edited(
            self, infile, snapshot_run):
        """A snippet's contents may be edited."""
        actions = (
            ['down']              # Move to Snippet 2
            + ['e']               # Edit it
            + ['end']
            + list(' - edited')
            + ['ctrl+s']
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
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_a_snippet_can_be_duplicated(
            self, infile, snapshot_run):
        """A snippet's contents may be duplicated and immediately edited."""
        actions = (
            ['down'] * 2          # Move to Snippet 3
            + ['d']               # Duplicate and edit it
            + ['end']
            + ['backspace']
            + ['4']
            + ['ctrl+s']
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
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_editing_maintains_folded_state(
            self, two_group_infile, edit_text_file, snapshot_run):
        """Folded groups remain folded after editing."""
        populate(edit_text_file, 'Snippet 2 - edited')
        actions = (
            ['left']                         # Move to first group.
            + ['down']                       # ... then next group.
            + ['f']                          # ... then fold.
            + ['up']                         # ... back to first group.
            + ['right']                      # ... then snippet.
            + ['down']                       # ... then second snippet.
            + ['e']                          # Edit it
            + ['end']
            + ['backspace']
            + ['B']
            + ['ctrl+s']
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            Snippet: 'Snippet 1'
            Snippet: 'Snippet B'
            MarkdownSnippet: 'Snippet 3'
            Group: Third
            KeywordSet:
            MarkdownSnippet: 'Snippet 4'
        ''')
        runner, snapshot_ok = await snapshot_run(two_group_infile, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_clipboard_can_be_edited(
            self, infile, snapshot_run):
        """The prepared clipboard content can be edited."""
        actions = (
            ['down']              # Move to Snippet 2
            + ['enter']           # Add to the clipboard
            + ['f2']              # Edit the clipboard preview
            + ['end']
            + list(' - edited')
            + ['ctrl+s']
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_editing_can_be_abandoned(
            self, infile, snapshot_run):
        """The editor may be quit, abandoning changes."""
        actions = (
            ['down']              # Move to Snippet 2
            + ['e']               # Edit it
            + ['end']
            + list(' - edited')
            + ['ctrl+q']
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
    async def test_a_new_snippet_can_be_added_to_and_empty_group(
            self, empty_group_infile, edit_text_file, snapshot_run):
        """A snippet may be added to an empty group."""
        populate(edit_text_file, 'New snippet')
        actions = (
            ['a']               # Add and edit it
            + list('New snippet')
            + ['ctrl+s']
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            MarkdownSnippet: 'New snippet'
        ''')
        runner, snapshot_ok = await snapshot_run(empty_group_infile, actions)
        assert expect == runner.app.root.full_repr()
        assert '' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'
