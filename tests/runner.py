"""Simple wrapper to run Snippets for snapshot tests."""

import sys


from snippets import core

args = core.parse_args()
app = core.Snippets(args)
