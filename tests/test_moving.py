"""Moving the snippets within and between gruops."""
from __future__ import annotations
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name

import pytest

from support import clean_text, populate

# TODO:
#   Tests should involve preserved text. Currently, I think that code will
#   break when preserved text is around and things get moved.
#
#   However, I am not sure that preserving text is really a good idea. Perhaps
#   we should allow comments, but then treat the file a read-only or issue a
#   warning that comments in the input file will be lost.

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
    Second:Third
      @text@
        Snippet 4
      @text@
        Snippet 5
'''
empty_sub_group_text = '''
    Main
      @text@
        Snippet 1
      @text@
        Snippet 2
      @text@
        Snippet 3
    Second
    Second:Third
'''
long_infile_text = std_infile_text + '''
      @text@
        Snippet 8
      @text@
        Snippet 9
      @text@
        Snippet 10
      @text@
        Snippet 11
      @text@
        Snippet 12
      @text@
        Snippet 13
      @text@
        Snippet 14
'''
single_snippet_text = '''
    Main
      @text@
        Snippet 1
'''
zero_snippet_text = '''
    Main
      @text@
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


@pytest.fixture
def infile_g0x2(snippet_infile):
    """Create a input file with an empty group and empty sub-group."""
    populate(snippet_infile, empty_sub_group_text)
    return snippet_infile


@pytest.fixture
def longfile(snippet_infile):
    """Create a standard input file for scrolling tests."""
    populate(snippet_infile, long_infile_text)
    return snippet_infile


@pytest.fixture
def single_snippet(snippet_infile):
    """Create a standard input file with just one snippet."""
    populate(snippet_infile, single_snippet_text)
    return snippet_infile


@pytest.fixture
def zero_snippets(snippet_infile):
    """Create a standard input file with no snippets."""
    populate(snippet_infile, zero_snippet_text)
    return snippet_infile


@pytest.fixture(params=range(7))
def n_moves(request) -> list:
    """Generate fixtures for various numbers of moves."""
    return request.param


class TestKeyboardControlled:
    """Using the keyboard as much as possible."""

    @pytest.mark.asyncio
    async def test_move_snippet_within_group(self, infile, snapshot_run_dyn):
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
        runner, snapshot_ok = await snapshot_run_dyn(infile, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_snippet_to_start_of_group(
            self, infile, snapshot_run_dyn):
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
        runner, snapshot_ok = await snapshot_run_dyn(infile, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_snippet_to_end_of_group(
            self, infile, snapshot_run_dyn):
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
        runner, snapshot_ok = await snapshot_run_dyn(infile, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_snippet_between_groups(self, infile, snapshot_run):
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
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_snippet_to_other_group_start(
            self, infile, snapshot_run):
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
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_snippet_to_other_group_end(self, infile, snapshot_run):
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
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_can_empty_a_group(self, infile_g1, snapshot_run):
        """A snippet move may leave a gruop empty."""
        actions = (
            ['down'] * 2          # Move to Snippet 3
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
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_can_insert_in_an_empty_group(
            self, infile_g0, snapshot_run):
        """A snippet move may insert into an empty group."""
        actions = (
            ['down'] * 2          # Move to Snippet 3
            + ['m']               # Start moving
            + ['down'] * 1        # Move insertion point to next group
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
            Group: Second:Third
            KeywordSet:
            Snippet: 'Snippet 4'
            Snippet: 'Snippet 5'
        ''')
        runner, snapshot_ok = await snapshot_run(infile_g0, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_can_insert_in_a_sub_group(
            self, infile_g0, snapshot_run):
        """A snippet move may insert into a sub-group."""
        actions = (
            ['down'] * 2          # Move to Snippet 3
            + ['m']               # Start moving
            + ['down'] * 2        # Move insertion point to sub-group.
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
            Group: Second:Third
            KeywordSet:
            Snippet: 'Snippet 3'
            Snippet: 'Snippet 4'
            Snippet: 'Snippet 5'
        ''')
        runner, snapshot_ok = await snapshot_run(infile_g0, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_can_insert_in_an_empty_sub_group(
            self, infile_g0x2, snapshot_run):
        """A snippet move may insert into an empty sub-group."""
        actions = (
            ['down'] * 2          # Move to Snippet 3
            + ['m']               # Start moving
            + ['down'] * 2        # Move insertion point to sub-group.
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
            Group: Second:Third
            KeywordSet:
            Snippet: 'Snippet 3'
        ''')
        runner, snapshot_ok = await snapshot_run(infile_g0x2, actions)
        assert expect == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_insertion_point_is_visible(
            self, infile, snapshot_run, n_moves):
        """The insertion point is clearly shown - moving down."""
        actions = (
            ['m']                    # Start moving
            + ['down'] * n_moves     # Move a number of times.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_insertion_point_is_visisble_top_of_1st_gruop(
            self, infile, snapshot_run):
        """The insertion point is clearly shown - top of first group."""
        actions = (
            ['down']                 # Move to Snippet 2
            + ['m']                  # Start moving
            + ['up']                 # Move up to top of first group.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_insertion_point_is_visisble_for_empty_group(
            self, infile_g0, snapshot_run):
        """The insertion point is clearly shown for an empty group."""
        actions = (
            ['m']                    # Start moving
            + ['down']  * 2          # Move to the empty group.
        )
        _, snapshot_ok = await snapshot_run(infile_g0, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_escape_cancels_move(self, infile, snapshot_run):
        """Pressing the ESC key cancels the move operation."""
        actions = (
            ['m']                    # Start moving
            + ['down'] * 2           # Move down a number of times.
            + ['escape']             # Cancel moving
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_view_scrolls_for_insertion_point(
            self, longfile, snapshot_run):
        """The view scrolls to ensure the insertion point remains visible."""
        actions = (
            ['m']                    # Start moving
            + ['down'] * 6           # Move down a number of times.
        )
        _, snapshot_ok = await snapshot_run(longfile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_view_scrolls_for_insertion_only_as_necessary(
            self, longfile, snapshot_run):
        """The view does not scroll unless necessary."""
        actions = (
            ['m']                    # Start moving
            + ['down'] * 5           # Move down a number of times.
        )
        _, snapshot_ok = await snapshot_run(longfile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_view_scrolls_for_insertion_point_up(
            self, longfile, snapshot_run):
        """The view scrolls to ensure the insertion point remains visible."""
        actions = (
            ['down'] * 2     # Move to snippet 3
            + ['m']          # Start moving
            + ['down'] * 6   # Move down a number of times.
            + ['up'] * 6     # Move to snippet 2.
        )
        _, snapshot_ok = await snapshot_run(longfile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_ignore_for_single_snippet(
            self, single_snippet, snapshot_run):
        """The move command is ignored for a single snippet file."""
        actions = (
            ['m']                    # Try to start moving
        )
        _, snapshot_ok = await snapshot_run(
            single_snippet, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'


class TestMouseControlled:
    """Generally preferring to use the mouse."""

    @pytest.fixture
    @staticmethod
    def std_result(snippet_infile):
        """Create a standard expected result."""
        return clean_text('''
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

    @pytest.mark.asyncio
    async def test_right_click_brings_up_context_menu(
            self, infile, snapshot_run_dyn):
        """A right click on a snippet brings up a context menu."""
        actions = (
            ['right:snippet-5']
        )
        _, snapshot_ok = await snapshot_run_dyn(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_right_click_brings_up_context_menu_for_group(
            self, infile, snapshot_run):
        """A right click on a group brings up a context menu."""
        actions = (
            ['right:group-1']         # Open group context menu.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_right_context_menu_can_be_quit(
            self, infile, snapshot_run_dyn):
        """The context menu can be quit, instead of selecting an action."""
        actions = (
            ['right:snippet-4']       # Open snippet-5 menu
            + ['left:cancel']         # Then just quit.
        )
        _, snapshot_ok = await snapshot_run_dyn(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_group_context_menu_can_be_quit(
            self, infile, snapshot_run):
        """A right click on a group brings up a context menu."""
        actions = (
            ['right:group-1']         # Open group context menu.
            + ['left:cancel']         # Then just quit.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_snippet_within_group(
            self, infile, snapshot_run, std_result):
        """A snippet may be moved within a group."""
        actions = (
            ['right:snippet-5']       # Open snippet-6 menu
            + ['left:move']           # Select move.
            + ['enter']               # Complete move
        )
        runner, snapshot_ok = await snapshot_run(infile, actions)
        assert std_result == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_meta_left_initiates_a_move(
            self, infile, snapshot_run_dyn, std_result):
        """Meta-left (alt-left) click on a snippet starts a move."""
        actions = (
            ['meta-left:snippet-5']    # Start moving snippet-6
            + ['enter']                # Complete move
        )
        runner, snapshot_ok = await snapshot_run_dyn(infile, actions)
        assert std_result == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'

    @pytest.mark.asyncio
    async def test_move_snippet_within_group_kb_buttons(
            self, infile, snapshot_run_dyn, std_result):
        """The keyboard may be used to select and press the menu buttons."""
        actions = (
            ['right:snippet-5']       # Open snippet-6 menu
            + ['tab'] * 3             # Select move.
            + ['enter']               # Activate the move button
            + ['enter']               # Complete move
        )
        runner, snapshot_ok = await snapshot_run_dyn(infile, actions)
        assert std_result == runner.app.root.full_repr()
        assert snapshot_ok, 'Snapshot does not match stored version'
