"""Simple script that performs file editing during tests."""

import os
import sys
from pathlib import Path

# The first argument is provided by the Clippets application code.
clippet_temp_path = Path(sys.argv[1])
old_text = clippet_temp_path.read_text(encoding='utf-8')

# The scond argument is provded by the test infrastructure. It oontains the
# text that shoulb be written to the Clippets provided file.
new_content_path = Path(os.environ['CLIPPETS_TEST_PATH'])
new_text = new_content_path.read_text(encoding='utf-8')

# The new text may have leading metedata. Remove it.
lines = new_text.splitlines()
while lines and lines[0].startswith('::'):
    lines.pop(0)
new_text = '\n'.join(lines)

# Write the new text to the Clippets provided file.
clippet_temp_path.write_text(new_text, encoding='utf-8')

# Write Usefule information to the test infrastructure file.
info = '::action occurred::\n'
info += old_text
new_content_path.write_text(info, encoding='utf-8')
