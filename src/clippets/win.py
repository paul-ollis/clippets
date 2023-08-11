"""Windows specific code.

Musch of this code is copied from pyperclip:

    (https://pypi.org/project/pyperclip)

and then edited to remove anythin that Snippets really does not need. It has
also undergone some changes resulting from quality tooling.

FUTURE: I want to support things like Wordpad formatted text.
"""
from __future__ import annotations
# ruff: noqa: N816

import contextlib
import ctypes
import os
import sys
import time
from ctypes import (
    Array, c_char, c_char_p, c_size_t, c_wchar, c_wchar_p, get_errno, sizeof)
from ctypes.wintypes import (
    BOOL, DWORD, HANDLE, HGLOBAL, HINSTANCE, HMENU, HWND, INT, LPCSTR, LPVOID,
    UINT)
from pathlib import Path

import markdown

doc_template = r'''
Version:0.9
StartHTML:{0:08d}
EndHTML:{1:08d}
StartFragment:{2:08d}
EndFragment:{3:08d}
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
<!--StartFragment-->
{4}
<!--EndFragment-->
</body>
</html>
'''.lstrip()
s = doc_template.format(0, 0, 0, 0, '')
START_HTML = s.index('<html>')
END_HTML = s.index('</html>') + 7
START_FRAGMENT = s.index('<!--EndFragment-->') - 1
del s


class ClipboardError(Exception):
    """Inidication that clipboard access failed."""


class CheckedCall:                     # pylint: disable=too-few-public-methods
    """Wrapper to invoke and check a windows API function."""

    def __init__(self, f, argtypes, restype):
        self.f = f
        self.f.argtypes = argtypes
        self.f.restype = restype

    def __call__(self, *args):
        """Invoke function and check the result."""
        ret = self.f(*args)
        if not ret and get_errno():
            raise ClipboardError('Error calling ' + self.f.__name__)
        return ret


windll = ctypes.windll                             # type: ignore[attr-defined]
msvcrt = ctypes.CDLL('msvcrt')

cc = CheckedCall
safeCreateWindowExA = cc(
    windll.user32.CreateWindowExA,
    [
        DWORD, LPCSTR, LPCSTR, DWORD, INT, INT, INT, INT, HWND, HMENU,
        HINSTANCE, LPVOID],
    HWND)
safeDestroyWindow = cc(windll.user32.DestroyWindow, [HWND], BOOL)
safeGlobalAlloc = cc(
    windll.kernel32.GlobalAlloc, [UINT, c_size_t], HGLOBAL)
safeGlobalLock = cc(windll.kernel32.GlobalLock, [HGLOBAL], LPVOID)
safeGlobalUnlock = cc(windll.kernel32.GlobalUnlock, [HGLOBAL], BOOL)
wcslen = cc(msvcrt.wcslen, [c_wchar_p], UINT)
strlen = cc(msvcrt.strlen, [c_char_p], UINT)
getLastError = cc(windll.kernel32.GetLastError, [], UINT)

# Clipboard functions.
OpenClipboard           = cc(windll.user32.OpenClipboard, [HWND], BOOL)
CountClipboardFormats   = cc(windll.user32.CountClipboardFormats, [], INT)
EnumClipboardFormats    = cc(windll.user32.EnumClipboardFormats , [UINT], UINT)
GetClipboardFormatName  = cc(windll.user32.GetClipboardFormatNameA ,
                             [UINT, LPCSTR, INT], INT)
CloseClipboard          = cc(windll.user32.CloseClipboard, [], BOOL)
EmptyClipboard          = cc(windll.user32.EmptyClipboard, [], BOOL)
GetClipboardData        = cc(windll.user32.GetClipboardData, [UINT], HANDLE)
SetClipboardData        = cc(windll.user32.SetClipboardData, [UINT, HANDLE],
                             HANDLE)
RegisterClipboardFormat = cc(windll.user32.RegisterClipboardFormatA, [LPCSTR],
                             UINT)

GMEM_MOVEABLE = 0x0002
CF_UNICODETEXT = 13
CF_HTML = RegisterClipboardFormat(c_char_p(b'HTML Format'))
CF_UNICODETEXT = 13


@contextlib.contextmanager
def window():
    """Context that provides a valid Windows handle."""
    # we really just need the hwnd, so setting 'STATIC'
    # as predefined lpClass is just fine.
    hwnd = safeCreateWindowExA(
        0, b'STATIC', None, 0, 0, 0, 0, 0, None, None, None, None)
    try:
        yield hwnd
    finally:
        safeDestroyWindow(hwnd)


@contextlib.contextmanager
def clipboard():
    """Context manager that opens the clipboard exclusively.

    This prevents other applications from modifying the clipboard content.
    """
    # We may not get the clipboard handle immediately because
    # some other application is accessing it (?)
    # We try for at least 500ms to get the clipboard.
    with window() as hwnd:
        t = time.time() + 0.5
        success = False
        while time.time() < t:
            success = OpenClipboard(hwnd)
            if success:
                break
            time.sleep(0.01)
        if not success:
            msg = 'Error calling OpenClipboard'
            raise ClipboardError(msg)

        try:
            yield
        finally:
            CloseClipboard()


def copy_windows(_format_code: int, text: str):
    """Copy text to the windows clipboard."""
    # This function is heavily based on
    # http://msdn.com/ms649016#_win32_Copying_Information_to_the_Clipboard
    if not text:
        return

    # http://msdn.com/ms649048
    # If an application calls OpenClipboard with hwnd set to NULL,
    # EmptyClipboard sets the clipboard owner to NULL; this causes
    # SetClipboardData to fail.
    #
    # We need a valid hwnd to copy something.
    with clipboard():
        EmptyClipboard()
        put_ascii(CF_HTML, text.encode())
        put_unicode(text)


@contextlib.contextmanager
def locked_clipboard_data(fmt):
    """Acquire loacked access to clipboard data."""
    h = GetClipboardData(fmt)
    yield safeGlobalLock(h)
    safeGlobalUnlock(h)


def dump_clipboard(text='', f=sys.stdout, *, show_html=False):     # noqa: C901
    """Dump the clipboard contents to a file.

    This was critical to me when grokking the correct formatting to put HTML
    into the clipboard.
    """
    if text:
        print(text, file=f)
    print(f'Formats = {CountClipboardFormats()}', file=f)

    fmt = 0
    content = {}
    with clipboard():
        while True:
            dp : Array[c_char] | Array[c_wchar]
            chars: str | bytes

            fmt = EnumClipboardFormats(fmt)
            if fmt == 0:
                print('END', getLastError())
                break
            dp = ctypes.create_string_buffer(b' ' * 30)
            n = GetClipboardFormatName(fmt, dp, len(dp))
            name = b''.join(dp)[:n]
            print(f'    {fmt}: {name!r}', file=f)

            with locked_clipboard_data(fmt) as lh:
                if lh is None:
                    print('        inaccessible?')
                else:
                    is_html = name in (b'text/html', b'HTML Format')
                    if name.startswith(b'text/'):
                        pw = c_wchar_p(lh)
                        n = wcslen(pw)
                        nw = n * sizeof(c_wchar)
                        dp = ctypes.create_unicode_buffer(nw + 1)
                        ctypes.memmove(dp, pw, nw + 1)
                        chars = ''.join(dp)[:n]
                        if is_html:
                            content[fmt] = chars
                    else:
                        pb = c_char_p(lh)
                        n = strlen(pb)
                        dp = ctypes.create_string_buffer(n + 1)
                        ctypes.memmove(dp, pb, n)
                        chars = b''.join(dp)[:n]
                        if is_html:
                            try:
                                content[fmt] = chars.decode()
                            except UnicodeError:
                                content[fmt] = f'{chars!r}'
                    print(f'        {pb} {n} {chars[:70]!r}', file=f)

    if content and show_html:
        print(f'MY HTML = {CF_HTML}', file=f)
        for fmt, val in content.items():
            print(f'\n{fmt}:', file=f)
            print(val, file=f)


def dump_clipboard_to_fred(text):
    """Dump the clipboard contents to a file."""
    with Path('fred.txt').open('w', encoding='utf-8') as f:
        dump_clipboard(text, f)


def put_ascii(format_code, text):
    """Copy ASCII (bytes) string to the clipboard."""
    count = strlen(text) + 1
    h = safeGlobalAlloc(GMEM_MOVEABLE, count + 1)
    lh = safeGlobalLock(h)
    ctypes.memmove(c_char_p(lh), c_char_p(text), count)
    safeGlobalUnlock(h)
    SetClipboardData(format_code, h)


def put_unicode(text):
    """Copy unicode string to the clipboard.

    This is unused and untested.
    """
    count = wcslen(text) + 1
    h = safeGlobalAlloc(GMEM_MOVEABLE, count * sizeof(c_wchar))
    lh = safeGlobalLock(h)
    ctypes.memmove(c_wchar_p(lh), c_wchar_p(text), count * sizeof(c_wchar))
    safeGlobalUnlock(h)
    SetClipboardData(CF_UNICODETEXT, h)


def put_to_clipboard(text: str, mode: str = 'styled'):
    """Put a text string into the clipboard."""
    if mode == 'raw':
        copy_windows(CF_UNICODETEXT, text)
    else:
        html = markdown.markdown(text)
        n = len(html)
        html = doc_template.format(
            START_HTML, END_HTML + n, START_FRAGMENT,  START_FRAGMENT + n + 1,
            html)
        copy_windows(CF_HTML, html)


@contextlib.contextmanager
def terminal_title(_title: str):
    """Temporarily set the text terminal's title.

    This currently does nothing on Windows.
    """
    yield None


def get_editor_command(env_var_name: str, default: str | None = None) -> str:
    """Get the editor command using a given environment variable name.

    If the environment variable is not set, this uses notepad.
    """
    if default is None:
        default = 'notepad'
    return os.getenv(env_var_name, default)


def get_winpos() -> tuple[int, int]:
    """Get the screen position of the terminal."""
    return 0, 0
