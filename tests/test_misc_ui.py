"""Miscellaneous user interface behaviour."""
from __future__ import annotations
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name

from pathlib import Path

import pytest

from support import clean_text, fix_named_temp_file, populate

from clippets import core

HERE = Path(__file__).parent
std_infile_text = '''
    @title: Just testing.
    Main [tag-a tag-b]
      @text@
        Snippet 1
    Second [tag-b tag-c]
      @text@
        Snippet 2
    Second : Child A [tag-b]
      @md@
        Snippet A2
    Second : Child B [tag-b]
      @text@
        Snippet B2
    Third [tag-c tag-a]
      @text@
        Snippet 3
'''


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


class TestMouseControlled:
    """Mainly mouse based control."""

    @pytest.mark.asyncio
    async def test_the_snippet_under_the_mouse_is_highlighed(
            self, infile, snapshot_run):
        """When the mose is over a snippet, it is highlighted.

        The highlight is distinct from the added snippets.
        """
        actions = (
            ['left:snippet-1']            # Add Snippet 2 to clipboard.
            + ['hover:snippet-2']         # Hover over Snippet A2
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_selected_snippets_also_show_highlight(
            self, infile, snapshot_run):
        """When the mose is over am added snippet, it is highlighted.

        The highlight is distinct from the other added snippets.
        """
        actions = (
            ['left:snippet-1']            # Add Snippet 2 to clipboard.
            + ['left:snippet-3']          # Add Snippet B2 to clipboard.
            + ['hover:snippet-1']         # Hover over Snippet 2
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_highlight_disappears_as_necessary(
            self, infile, snapshot_run):
        """When the mose is over no snippet there is no highlight."""
        actions = (
            ['hover:group-3']            # Hover over Child A
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'


class TestBootstrapping:
    """When a user runs Clippets for the first time."""

    @pytest.mark.asyncio
    async def test_nonexistant_file_offers_basic_template(
            self, snapshot_run):
        """If started with a non-existant file, a simple template is offered.

        The template has 2 groups and 3 snippets.
        """
        actions = (
        )
        with fix_named_temp_file('test-snippets.txt') as infile:
            _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_user_can_quit_for_nonexistant_file(
            self, infile, simple_run):
        """If started with a non-existant file, the user can choose to quit."""
        actions = (
            ['tab']
            + ['enter']
        )
        infile.delete()
        _, exited = await simple_run(infile, actions, expect_exit=True)
        assert exited

    @pytest.mark.asyncio
    async def test_user_can_accept_template_for_new_file(
            self, infile, edit_text_file, snapshot_run):
        """The user can opt to continue with the new template file."""
        populate(edit_text_file, 'Snippet 1 - edited')
        actions = (
            ['enter']              # Accept the template.
            + ['e']                # Edit a snippet.
            + ['wait:0.5:EditorHasExited']
        )
        infile.delete()
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert not runner.exited
        assert 'My first snippet.' == edit_text_file.prev_text
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_defaulted_file_is_monitored_for_changes(
            self, infile, edit_text_file, snapshot_run):
        """A created default file is monitored for changes."""

        def update_file():
            text = std_infile_text.replace(
                'My second snippet', 'Snippet 2.')
            populate(infile, text)

        populate(edit_text_file, 'Snippet 1 - edited X')
        actions = (
            ['enter']              # Accept the template.
            + ['e']                # Edit a snippet.
            + ['wait:0.5:EditorHasExited']
            + [update_file]        # Change the file.
            + ['pause:0.2']
        )
        expect = clean_text('''
            Group: <ROOT>
            KeywordSet:
            Group: Main
            KeywordSet:
            MarkdownSnippet: 'Snippet 1 - edited X'
            MarkdownSnippet: 'My second snippet.'
            Group: Second
            KeywordSet:
            MarkdownSnippet: 'My third snippet.'
        ''')
        infile.delete()
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert not runner.exited
        assert 'My first snippet.' == edit_text_file.prev_text
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_failure_to_read_file_is_handled(
            self, infile, simple_run):
        """Clippets gracefully handles failure to read the file."""
        actions = ()
        Path(infile.name).chmod(0o222)
        with pytest.raises(core.StartupError) as info:
            await simple_run(infile, actions)
        expect = f'Could not open {infile.name}: Permission denied'
        assert expect == str(info.value)
