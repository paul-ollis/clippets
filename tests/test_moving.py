"""Moving the snippets within and between gruops."""
from __future__ import annotations
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name

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
    Third
      @text@
        Snippet 4
      @text@
        Snippet 5
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
    """Create a standard input file with no znippets."""
    populate(snippet_infile, zero_snippet_text)
    return snippet_infile


@pytest.fixture(params=range(7))
def n_moves(request) -> list:
    """Generate fixtures for various numbers of moves."""
    return request.param


# TODO: Remove this when I am happy the code tests are stable.
def gen_moves(move, n):
    """Generate move and delay actions."""
    fast_n = 6
    moves_a = [move] * min(fast_n, n)
    # moves_b = [move, 'pause:0.01'] * max(0, n - fast_n)
    moves_b = [move] * max(0, n - fast_n)
    return moves_a + moves_b


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
        assert expect == runner.app.groups.full_repr()
        assert snapshot_ok


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
        assert expect == runner.app.groups.full_repr()
        assert snapshot_ok


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
        assert expect == runner.app.groups.full_repr()
        assert snapshot_ok


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
        assert expect == runner.app.groups.full_repr()
        assert snapshot_ok


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
        assert expect == runner.app.groups.full_repr()
        assert snapshot_ok


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
        assert expect == runner.app.groups.full_repr()
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_move_can_empty_a_group(self, infile_g1, snapshot_run):
        """A snippet move may leave a gruop empty."""
        actions = (
            ['down'] * 2          # Move to Snippet 6
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
        assert expect == runner.app.groups.full_repr()
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_move_can_insert_in_an_empty_group(
            self, infile_g0, snapshot_run):
        """A snippet move may leave a gruop empty."""
        actions = (
            ['down'] * 2          # Move to Snippet 6
            + ['m']               # Start moving
            + ['down'] * 1          # Move insetion point to prev group
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
            Group: Third
            KeywordSet:
            Snippet: 'Snippet 4'
            Snippet: 'Snippet 5'
        ''')
        runner, snapshot_ok = await snapshot_run(infile_g0, actions)
        assert expect == runner.app.groups.full_repr()
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_insertion_point_is_visisble(
            self, infile, snapshot_run, n_moves):
        """The inserrtion point is clearly shown - moving down."""
        actions = (
            ['m']                    # Start moving
            + ['down'] * n_moves     # Move a number of times.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_insertion_point_is_visisble_top_of_1st_gruop(
            self, infile, snapshot_run):
        """The inserrtion point is clearly shown - top of first group."""
        actions = (
            ['down']                 # Move to Snippet 2
            + ['m']                  # Start moving
            + ['up']                 # Move up to top of first group.
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_insertion_point_is_visisble_for_empty_group(
            self, infile_g0, snapshot_run):
        """The inserrtion point is clearly shown for an empty group."""
        actions = (
            ['m']                    # Start moving
            + ['down']  * 2          # Move to the empty group.
            # + ['pause:0.1']
        )
        _, snapshot_ok = await snapshot_run(infile_g0, actions)
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_escape_cancels_move(self, infile, snapshot_run):
        """Pressing the ESC key cancels the move operation."""
        actions = (
            ['m']                    # Start moving
            + ['down'] * 2           # Move down a number of times.
            + ['escape']             # Cancel moving
        )
        _, snapshot_ok = await snapshot_run(infile, actions)
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_view_scrolls_for_insertion_point(
            self, longfile, snapshot_run):
        """The view scrolls to ensure the inserrtion point remains visible."""
        actions = (
            ['m']                    # Start moving
            + gen_moves('down', 6)   # Move down a number of times.
        )
        _, snapshot_ok = await snapshot_run(longfile, actions, post_delay=0.15)
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_view_scrolls_for_insertion_only_as_necessary(
            self, longfile, snapshot_run):
        """The view does not scroll unless necessary."""
        actions = (
            ['m']                    # Start moving
            + gen_moves('down', 5)   # Move down a number of times.
        )
        _, snapshot_ok = await snapshot_run(longfile, actions)
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_view_scrolls_for_insertion_point_up(
            self, longfile, snapshot_run):
        """The view scrolls to ensure the inserrtion point remains visible."""
        actions = (
            gen_moves('down', 2)     # Move to snippet 3
            + ['m']                  # Start moving
            + gen_moves('down', 6)   # Move down a number of times.
            + gen_moves('up', 6)     # Move to snippet 2.
        )
        _, snapshot_ok = await snapshot_run(longfile, actions, post_delay=0.20)
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_move_ignore_for_single_snippet(
            self, single_snippet, snapshot_run):
        """The move command is ignored for a single snippet file."""
        actions = (
            ['m']                    # Try to start moving
        )
        _, snapshot_ok = await snapshot_run(
            single_snippet, actions, post_delay=0.20)
        assert snapshot_ok


    @pytest.mark.asyncio
    async def test_move_ignore_for_zero_snippets(
            self, zero_snippets, snapshot_run):
        """The move command is ignored for a zero snippet file."""
        actions = (
            ['m']                    # Try to start moving
        )
        _, snapshot_ok = await snapshot_run(
            zero_snippets, actions, post_delay=0.20)
        assert snapshot_ok


class TestMouseControlled:
    """Generally preferring to use the mouse."""

    @pytest.fixture
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
        """A right click on a snippet brings up a context menu.

        One option provided is to move the snippet.
        """
        actions = (
            ['right:snippet-5']
        )
        _, snapshot_ok = await snapshot_run_dyn(infile, actions)
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_right_context_menu_can_be_quit(
            self, infile, snapshot_run_dyn):
        """The context menu can be quit, instead of selecting an action."""
        actions = (
            ['right:snippet-4']       # Open snippet-5 menu
            + ['left:cancel']         # Then just quit.
        )
        _, snapshot_ok = await snapshot_run_dyn(infile, actions)
        assert snapshot_ok

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
        assert std_result == runner.app.groups.full_repr()
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_meta_left_initiates_a_move(
            self, infile, snapshot_run_dyn, std_result):
        """Meta-left (alt-left) click on a snippet starts a move."""
        actions = (
            ['meta-left:snippet-5']    # Start moving snippet-6
            + ['enter']                # Complete move
        )
        runner, snapshot_ok = await snapshot_run_dyn(infile, actions)
        assert std_result == runner.app.groups.full_repr()
        assert snapshot_ok

    @pytest.mark.asyncio
    async def test_move_snippet_within_group_kb_buttons(
            self, infile, snapshot_run_dyn, std_result):
        """The keyboard may be used to select and press the menu buttons."""
        actions = (
            ['right:snippet-5']       # Open snippet-6 menu
            + ['tab'] * 2             # Select move.
            + ['enter']               # Activate the move button
            + ['enter']               # Complete move
        )
        runner, snapshot_ok = await snapshot_run_dyn(infile, actions)
        assert std_result == runner.app.groups.full_repr()
        assert snapshot_ok
