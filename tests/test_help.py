"""Clippets provides built-in help.

Currently this is fairly simple, consisting of a single, non-interactove page.
"""
from __future__ import annotations
# pylint: disable=redefined-outer-name

import os
from pathlib import Path

import pytest

from support import populate

from clippets import core, snippets

HERE = Path(__file__).parent
std_infile_text = '''
    Main [tag-a tag-b]
      @md@
        Markdown allows:

        - *Italic* text.
        - **Bold** text.
        - ***Bold italic*** text.

    Second [tag-b tag-c]
      @md@
        Snippet 2
    Second : Child A [tag-b]
      @md@
        Snippet A2
    Second : Child B [tag-b]
      @md@
        Snippet B2
    Third [tag-c tag-a]
      @md@
        Snippet 3
'''


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


@pytest.mark.asyncio
async def test_help_can_be_displayed(infile, snapshot_run):
    """The F1 key brings up a help page."""
    actions = (
        ['f1']            # Open the help
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_footer_click_show_help(infile, snapshot_run):
    """Clicking the help part of the footer brings up a help page."""
    actions = (
        ['left:.footer']            # Open the help
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'


@pytest.mark.asyncio
async def test_help_can_be_hidden(infile, snapshot_run):
    """The F1 is also used to close the help page."""
    actions = (
        ['f1'] * 2        # Open the help then close it.
    )
    _, snapshot_ok = await snapshot_run(infile, actions)
    assert snapshot_ok, 'Snapshot does not match stored version'
