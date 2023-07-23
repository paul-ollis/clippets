"""Paul's custom test configuration."""
from __future__ import annotations

import difflib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from typing import List, Union

import pytest
from _pytest.config import ExitCode
from _pytest.main import Session
from _pytest.terminal import TerminalReporter

from rich.console import Console

from fixtures import (
    save_svg_diffs, snapshot_run, snippet_infile, snippet_outfile, tempdir,
    work_file)

pytest_config = sys.modules['_pytest.config']

__all__ = (
    'snapshot_run',
    'snippet_infile',
    'snippet_outfile',
    'work_file',
)
pytest_plugins = ('rich', 'asyncio')


@dataclass
class DiffGroup:
    """A group of difference lines."""

    lines: list[str]
    code: str


def prep_diffs(l1, l2):                       # pylint: disable=too-many-locals
    """Prepare a set of diffenerce blocks.

    Each block stores a subset of the lines from the before and after lines.
    Each block groups lines according to whether thery are:

    unchanged
        Identical lines in before and after.
    context
        Identical lines in before and after, providing context around the
        following or preceding differene.
    deleted
        Lines only present in before.
    inserted
        Lines only present in after.
    replaced
        Lines that differ between before and after.
    """
    def app_lines(start, end, get_left=None, get_right=None):
        for _ in range(start, end):
            if get_left:
                lines[0].append(get_left())
            if get_right:
                lines[1].append(get_right())

    def app_diffs(tag):
        diffs[0].append(DiffGroup(lines[0], tag))
        diffs[1].append(DiffGroup(lines[1], tag))

    next_1 = partial(next, enumerate(l1))
    next_2 = partial(next, enumerate(l2))
    blank_line = partial(lambda: (-1, ''))

    diffs = [], []
    prev_a = 0
    for group in difflib.SequenceMatcher(a=l1, b=l2).get_grouped_opcodes():
        for tag, a, b, c, d in group:
            lines = [], []
            app_lines(prev_a, a, next_1, next_2)
            app_diffs('unchanged')
            prev_a = a

            lines = [], []
            if tag == 'equal':
                app_lines(a, b, next_1, next_2)
                app_diffs('context')
            elif tag == 'delete':
                app_lines(a, b, next_1, blank_line)
                app_diffs('deleted')
            elif tag == 'insert':
                app_lines(c, d, blank_line, next_2)
                app_diffs('inserted')
            elif tag == 'replace':
                app_lines(a, b, next_1, None)
                app_lines(c, d, None, next_2)
                app_lines(b - a, d - c, blank_line, None)
                app_lines(d - c, b - a, None, blank_line)
                app_diffs('replaced')

            prev_a = b

    return diffs


def lstr(idx: int):
    """Create line number label for a line in a file.

    :idx: The line index. If this is negative the label will be blank.
    """
    if idx < 0:
        return '     '
    else:
        return f'{idx + 1:>4}:'


def _strequals(config, op, left, right):
    return (
        op == '==' and isinstance(left, str) and isinstance(right, str)
        and config.pluginmanager.has_plugin('rich')
        and config.getoption("rich")
    )


def pytest_assertrepr_compare(config, op, left, right):
    """Customise certain type comparison reports."""
    # pylint: disable=too-many-locals
    if _strequals(config, op, left, right):
        s = ['<<--RICH-->>']
        lhs, rhs = prep_diffs(left.splitlines(), right.splitlines())
        for before, after in zip(lhs, rhs):
            for (ai, a), (bi, b) in zip(before.lines, after.lines):
                bar = '::'
                lhs_str = f'{a:<40}'
                rhs_str = f'{b}'
                err = '[bold red]E[/bold red] '

                if before.code == 'unchanged':
                    continue

                if before.code == 'context':
                    err = '[dim]c[/dim] '
                    bar = '=='
                elif before.code == 'deleted':
                    lhs_str = f'[bold red]{a:<40}[/bold red]'
                    bar = '[red bold]<-[/red bold]'
                elif before.code == 'inserted':
                    rhs_str = f'[yellow]{b}[/yellow]'
                    bar = '[yellow]->[/yellow]'
                elif before.code == 'replaced':
                    bar = '[green]<>[/green]'
                    lhs_str = f'[bold red]{a:<40}[/bold red]'
                    rhs_str = f'[yellow]{b}[/yellow]'

                s.append(
                    f'{err}{lstr(ai)} {lhs_str} {bar} {lstr(bi)} {rhs_str}')
        return s
    else:
        return None


def pytest_addoption(parser, pluginmanager):
    """Add my command line options."""
    group = parser.getgroup(
        'cs', 'CleverSheep options.')
    group.addoption(
        '--gen-doc', action='store_true',
        help='Generate test documentation.')


@pytest.fixture(autouse=True)
def clean_data(pytestconfig, monkeypatch):
    """Provide a common fixture for all tests."""


def pytest_configure(config: pytest.Config) -> None:
    """Perform any reuired global configuration."""


@contextmanager
def temp_command_args(args: List[str]):
    """Temporary update the arguments part od sys.argv."""
    saved = list(sys.argv)
    sys.argv[1:] = list(args)
    yield
    sys.argv[:] = saved


def pytest_sessionfinish(
    session: Session,
    exitstatus: Union[int, ExitCode],
) -> None:
    """Perform post run processing.

    After whole test run finished, right before returning the exit status to
    the system. Generates the snapshot report and writes it to disk.
    """
    if os.environ.get('PYTEST_XDIST_WORKER') is None:
        save_svg_diffs(session)
        tempdir.cleanup()


def pytest_terminal_summary(
    terminalreporter: TerminalReporter,
    exitstatus: ExitCode,
    config: pytest.Config,
) -> None:
    """Add a section to terminal summary reporting.

    Displays the link to the snapshot report that was generated in a prior
    hook.
    """
    diffs = getattr(config, "_textual_snapshots", None)
    console = Console(legacy_windows=False, force_terminal=True)
    if diffs:
        snapshot_report_location = config._textual_snapshot_html_report
        console.print("[b red]Textual Snapshot Report", style="red")
        console.print(
            f'\n[white on red]{len(diffs)} mismatched snapshots[/]\n'
            f'\n[b]View the [link=file://{snapshot_report_location}]'
            'failure report[/].\n'
        )
