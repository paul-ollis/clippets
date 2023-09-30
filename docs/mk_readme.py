"""Simple script to create README.rst.

The Sphinx documentation and README.txt share reStructureText, but Github
suppressed the ``.. include::`` directive. So this create the README.rst file
from a set of fragments.
"""

from pathlib import Path

source_names = '''
    README.txt
    credits.txt
'''

dest = Path('../README.rst')
sources = [Path(s) for s in source_names.split()]

with dest.open('w', encoding='utf-8') as f:
    f.write('.. vim: readonly nomodifiable\n')
    line = ''
    for i, p in enumerate(sources):
        if line.strip():
            f.write(f'\n')
        for line in p.read_text().splitlines():
            f.write(f'{line}\n')
