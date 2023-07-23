"""Simple script that performs file editing during tests."""

import os
import sys
from pathlib import Path

clippet_temp_path = Path(sys.argv[1])
new_content_path = Path(os.environ['CLIPPETS_TEST_PATH'])
old_text = clippet_temp_path.read_text(encoding='utf-8')
new_text = new_content_path.read_text(encoding='utf-8')
clippet_temp_path.write_text(new_text, encoding='utf-8')
new_content_path.write_text(old_text, encoding='utf-8')
