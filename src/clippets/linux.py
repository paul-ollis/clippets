"""Linux specific code."""
# ruff: noqa: N816

import contextlib
import os
import subprocess
import sys
from typing import Tuple

import markdown

doc_template = r'''
<html>
<head>
  <meta http-equiv='content-type' content='text/html; charset=utf-8'/>
  <title></title>
  <meta name='generator' content='LibreOffice 7.3.7.2 (Linux)'/>
  <style type='text/css'>
    @page {{ size: 21cm 29.7cm; margin: 2cm }}
    p {{ line-height: 115%; margin-bottom: 0.25cm; background: transparent }}
  </style>
</head>
<body lang='en-GB' link='#000080' vlink='#800000' dir='ltr'>
  <p style='line-height: 100%; margin-bottom: 0cm'>
{0}
</body>
</html>
'''

def put_to_clipboard(text: str, mode: str = 'styled'):
    """Put a text string into the clipboard."""
    if mode == 'raw':
        subprocess.run(
            ['/usr/bin/xclip', '-selection', 'clipboard'],
            input=text.encode(),
            check=False)
    else:
        html = markdown.markdown(text)
        html = doc_template.format(html)
        subprocess.run(
            ['/usr/bin/xclip', '-t', 'text/html', '-selection',
                'clipboard'],
            input=html.encode(),
            check=False)


@contextlib.contextmanager
def terminal_title(title: str):
    """Temporarily set the text terminal's title."""
    print('\x1b[22;0t', end='')
    print(f'\x1b]0;{title}\x07', end='')
    sys.stdout.flush()
    yield None
    print('\x1b[23;0t', end='')
    sys.stdout.flush()


def get_editor_command(env_var_name: str) -> str:
    """Get the editor command using a given envirot variable name.

    If the environment variable is not set, this uses gvim.
    """
    return os.getenv(env_var_name, 'gvim -f -geom {w}x{h}+{x}+{y}')


def get_winpos() -> Tuple[int, int]:                         # pragma: no cover
    """Get the screen position of the terminal."""
    res = subprocess.run(
        ['/usr/bin/xwininfo', '-name', 'Snippet-wrangler'],
        capture_output=True, check=False)
    for rawline in res.stdout.decode().splitlines():
        line = rawline.strip()
        if line.startswith('Absolute upper-left X:'):
            x = int(line.partition(':')[-1].strip())
        elif line.startswith('Absolute upper-left Y:'):
            y = int(line.partition(':')[-1].strip())
    return x, y
