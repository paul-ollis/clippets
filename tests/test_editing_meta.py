"""The effect of editing on metadata.

Clippets tries to preserve extra text in the input file. This allows user's
to add dcomments to the input file, which are preserved if they modify the
contents from within Clippets.
"""
from __future__ import annotations
# pylint: disable=redefined-outer-name

import pytest

from support import populate

from clippets import snippets

std_infile_text = '''
    # Main
    Main
      # Comment 1
      @text@
        Entry 1
      # Comment 2
      @text@
        Entry 2
    # Second
    Second
      # Comment 3
      @text@
        Entry 3
      # Comment 4
      @text@
        Entry 4
    # The end
'''


def load(path_name: str):
    """Load snippets from a file."""
    loader = snippets.Loader(path_name)
    *ret, _exc = loader.load()
    return ret


def save(path_name: str, root):
    """Load snippets from a file."""
    loader = snippets.Loader(path_name)
    return loader.save(root)


def move_text(text, *moves: list) -> str:
    """Peform some simple line based moves on some text."""
    lines = text.splitlines()
    for a, b, c in moves:
        sub = lines[a:b]
        lines[c:c] = sub
        del lines[a:b]

    return '\n'.join(lines) + '\n'


@pytest.fixture
def infile(snippet_infile):
    """Create a standard input file for many of this module's tests."""
    populate(snippet_infile, std_infile_text)
    return snippet_infile


def test_comments_are_preserved_from_load_to_save(
        snippet_infile, snippet_outfile):
    """Comments in various positions are preserved by loading and saving."""
    expected = populate(snippet_infile, '''
        # A leading comment.
        Main
          # Another comment
          @md@
            Snippet 1
        # A trailing comment.
    ''')
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    print(root.full_repr(details=True))
    assert expected == str(snippet_outfile)


@pytest.mark.asyncio
async def test_move_snippet(infile, simple_run):
    """A snippet's meta information moves with it."""
    actions = (
        ['m']                 # Start moving.
        + ['enter']           # Complete move.
    )
    expected = move_text(str(infile), [2, 5, 8])
    assert 0 == len(infile.backup_paths())
    await simple_run(infile, actions)
    assert 1 == len(infile.backup_paths())
    assert expected == str(infile)


@pytest.mark.asyncio
async def test_move_group(infile, simple_run):
    """A gruops's meta information moves with it."""
    actions = (
        ['left']              # Move to group.
        + ['m']               # Start moving.
        + ['enter']           # Complete move.
    )
    expected = move_text(str(infile), [0, 8, 16])
    assert 0 == len(infile.backup_paths())
    await simple_run(infile, actions)
    assert 1 == len(infile.backup_paths())
    assert expected == str(infile)
