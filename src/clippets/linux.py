"""Linux specific code."""
# ruff: noqa: N816

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from functools import partial

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


def get_editor_command(env_var_name: str, default: str | None = None) -> str:
    """Get the editor command using a given environment variable name.

    If the environment variable is not set, this uses gvim.
    """
    if default is None:
        default = 'gvim -f -geom {w}x{h}+{x}+{y}'
    return os.getenv(env_var_name, default)


def get_winpos() -> tuple[int, int]:                         # pragma: no cover
    """Get the screen position of the terminal."""
    capture = partial(
        subprocess.run, capture_output=True, check=False, text=True)
    res = capture(['/usr/bin/xprop', '-root', '32x', '_NET_ACTIVE_WINDOW'])
    _, _, wid = res.stdout.rpartition(' ')
    res = capture(['/usr/bin/xwininfo', '-id', wid])
    for rawline in res.stdout.splitlines():
        line = rawline.strip()
        if line.startswith('Absolute upper-left X:'):
            x = int(line.partition(':')[-1].strip())
        elif line.startswith('Absolute upper-left Y:'):
            y = int(line.partition(':')[-1].strip())
    try:
        return x, y
    except UnboundLocalError:
        return 0, 0


def dump_clipboard(_text='', _f=None):
    """Do nothing on Linux."""
