"""Snapshot tests to catch any regressions in the UI output.

This is currently just a place-holder.
"""

from support import populate


def xtest_snapshot(snippet_infile, snap_compare):
    """Play at getting snapshot tests working."""
    async def setup(app):
        pass

    populate(snippet_infile, '''
        Main
          @md@
            Snippet 1

        # Comment
        |
    ''')
    assert snap_compare(
        'runner.py', args=[snippet_infile.name], press=[])
