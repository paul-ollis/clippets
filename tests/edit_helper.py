"""Simple script that performs file editing during tests.

This involves two files:

- A temporary file created by the Clippets app (File-1), which is passed in
  sys,argv[1]. This contains the text that would be edited by the user in
  normal operation.

- A second temporary file created by the test framework (File-2). This is
  passed using the environment variable CLIPPETS_TEST_PATH. This file contains
  the text that will replace the contents of File-1.

The contents a File-2 are replaced by information that can be used by the
executing test. The current format is:

    ::action occurred::
    <original text of File-1>

If the environment variable CLIPPETS_TEST_WATCH_FILE is set then the program
will only exit once the identified file ceases to exist. It will check for the
file existance about 100 times per second.
"""

import os
import sys
import time
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

# Write Useful information to the test infrastructure file.
info = '::action occurred::\n'
info += old_text
new_content_path.write_text(info, encoding='utf-8')

watch_file_pathname = os.environ.get('CLIPPETS_TEST_WATCH_FILE', '')
if watch_file_pathname:
    p = Path(watch_file_pathname)
    while p.exists():
        time.sleep(0.01)
