"""Simple wrapper to run Clippets for snapshot tests."""

import sys


from clippets import core

args = core.parse_args()
app = core.Clippets(args)
