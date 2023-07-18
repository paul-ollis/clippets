"""Windows specific code.

Musch of this code is copied from pyperclip
(https://pypi.org/project/pyperclip) and then edited to temove anythin that
Snippets really does not need.

FUTURE: I want to support HTML formatted text.
"""
# ruff: noqa: N816

import asyncio
import contextlib
import ctypes
import os
import time
from ctypes import c_char_p, c_size_t, c_wchar, c_wchar_p, get_errno, sizeof
from ctypes.wintypes import (
    BOOL, DWORD, HANDLE, HGLOBAL, HINSTANCE, HMENU, HWND, INT, LPCSTR, LPVOID,
    UINT)
from pathlib import Path
from typing import Tuple

import markdown
from textual.drivers.windows_driver import WindowsDriver, WriterThread, win32

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


class CheckedCall:
    """Wrapper to invokke and cehck a windows API function."""

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


windll = ctypes.windll
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
s = c_char_p(b'HTML Format')
CF_HTML = RegisterClipboardFormat(s)


@contextlib.contextmanager
def window():
    """Context that provides a valid Windows hwnd."""
    # we really just need the hwnd, so setting 'STATIC'
    # as predefined lpClass is just fine.
    hwnd = safeCreateWindowExA(
        0, b'STATIC', None, 0, 0, 0, 0, 0, None, None, None, None)
    try:
        yield hwnd
    finally:
        safeDestroyWindow(hwnd)


@contextlib.contextmanager
def clipboard(hwnd):
    """Context manager that opens the clipboard excllusively.

    Tghis prevents other applications from modifying the clipboard content.
    """
    # We may not get the clipboard handle immediately because
    # some other application is accessing it (?)
    # We try for at least 500ms to get the clipboard.
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
    with window() as hwnd, clipboard(hwnd):
        EmptyClipboard()
        put_ascii(CF_HTML, text.encode())


def dump_clipboard(text):
    """Dump the clipboard contents to a file.

    This was critical to me when grikking the correct formatting to put HTML
    into the clipboard.
    """
    with Path('fred.txt').open('w') as f:
        f.write(text)
        n = CountClipboardFormats()
        print(f'Formats = {n}', file=f)

        fmt = 0
        content = {}
        while True:
            fmt = EnumClipboardFormats(fmt)
            if fmt == 0:
                break
            p = ctypes.create_string_buffer(b' ' * 30)
            n = GetClipboardFormatName(fmt, p, len(p))
            name = b''.join(p)[:n]
            print(f'    {fmt}: {name}', file=f)

            if name in (b'text/html', b'HTML Format'):
                h = GetClipboardData(fmt)
                lh = safeGlobalLock(h)
                if name.startswith(b'text/'):
                    p = c_wchar_p(lh)
                    n = wcslen(p)
                    nw = n * sizeof(c_wchar)
                    dp = ctypes.create_unicode_buffer(nw + 1)
                    ctypes.memmove(dp, p, nw + 1)
                    chars = ''.join(dp)[:n]
                    content[fmt] = chars
                else:
                    p = c_char_p(lh)
                    n = strlen(p)
                    dp = ctypes.create_string_buffer(n + 1)
                    ctypes.memmove(dp, p, n)
                    chars = b''.join(dp)[:n]
                    content[fmt] = chars.decode()
                print(f'        {p} {n} {chars[:10]}', file=f)
                safeGlobalUnlock(h)

        print(f'MY HTML = {CF_HTML}', file=f)
        for fmt, text in content.items():
            print(f'\n{fmt}:', file=f)
            print(text, file=f)


def put_ascii(format_code, text):
    """Copy ASCII (bytes) string to the clipboard."""
    count = strlen(text) + 1
    h = safeGlobalAlloc(GMEM_MOVEABLE, count + 1)
    lh = safeGlobalLock(h)
    ctypes.memmove(c_char_p(lh), c_char_p(text), count)
    safeGlobalUnlock(h)
    SetClipboardData(format_code, h)


def put_unicode(format_code, text):
    """Copy unicode string to the clipboard.

    This is unused and untested.
    """
    count = wcslen(text) + 1
    h = safeGlobalAlloc(GMEM_MOVEABLE, count * sizeof(c_wchar))
    lh = safeGlobalLock(h)
    ctypes.memmove(c_wchar_p(lh), c_wchar_p(text), count * sizeof(c_wchar))
    safeGlobalUnlock(h)
    SetClipboardData(format_code, h)


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


def get_editor_command(env_var_name: str) -> str:
    """Get the editor command using a given envirot variable name.

    If the environment variable is not set, this uses notepad.
    """
    return os.getenv(env_var_name, 'notepad')


def get_winpos() -> Tuple[int, int]:
    """Get the screen position of the terminal."""
    return 0, 0


class Patch:
    """Definition of patched Textual functions."""

    def start_application_mode(self) -> None:
        """Start application mode."""
        loop = asyncio.get_running_loop()

        self._restore_console = win32.enable_application_mode()

        self._writer_thread = WriterThread(self._file)
        self._writer_thread.start()

        self.write('\x1b[?1049h')              # Enable alt screen
        self._enable_mouse_support()
        self.write('\x1b[?25l')                # Hide cursor
        self.write('\x1b[?1003h\n')
        self._enable_bracketed_paste()

        self._event_thread = win32.EventMonitor(
            loop, self._app, self.exit_event, self.process_event)
        self._event_thread.start()

    def stop_application_mode(self) -> None:
        """Stop application mode, restore state."""
        self._disable_bracketed_paste()
        self.disable_input()

        # Disable alt screen, show cursor
        self.write('\x1b[?1049l' + '\x1b[?25h')                 # noqa: ISC003
        self.flush()

    def close(self) -> None:
        """Perform cleanup."""
        if self._writer_thread is not None:
            self._writer_thread.stop()
        if self._restore_console:
            self._restore_console()


WindowsDriver.stop_application_mode = Patch.stop_application_mode
WindowsDriver.start_application_mode = Patch.start_application_mode
WindowsDriver.close = Patch.close
