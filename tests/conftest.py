"""Paul's custom test configuration."""

import os
import sys
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime
from operator import attrgetter
from os import PathLike
from pathlib import Path, PurePath
from typing import Awaitable, Callable, Iterable, List, Optional, Union

import pytest
from _pytest.config import ExitCode
from _pytest.fixtures import FixtureRequest
from _pytest.main import Session
from _pytest.terminal import TerminalReporter
from jinja2 import Template

from rich.console import Console
from textual._doc import take_svg_screenshot
from textual._import_app import import_app
from textual.app import App
from textual.pilot import Pilot

from syrupy import SnapshotAssertion

from fixtures import snippet_infile, snippet_outfile, gen_tempfile

pytest_config = sys.modules['_pytest.config']


__all__ = (
    'snippet_infile', 'snippet_outfile',
)
pytest_plugins = ('pytest_rich',)
TEXTUAL_SNAPSHOT_SVG_KEY = pytest.StashKey[str]()
TEXTUAL_ACTUAL_SVG_KEY = pytest.StashKey[str]()
TEXTUAL_SNAPSHOT_PASS = pytest.StashKey[bool]()
TEXTUAL_APP_KEY = pytest.StashKey[App]()


def pytest_assertrepr_compare(op, left, right):
    """Customise certain type comparison reports."""


def pytest_addoption(parser, pluginmanager):
    """Add my command line options."""
    print("ADD OPTIONS")
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


@pytest.fixture
def snap_compare(
    snapshot: SnapshotAssertion, request: FixtureRequest
) -> Callable[[str | PurePath], bool]:
    """Create a fixture to run code and check the terminal output.

    This fixture returns a function which can be used to compare the output of
    a Textual app with the output of the same app in the past. This is snapshot
    testing, and it used to catch regressions in output.
    """

    def compare(
        app_path: str | PurePath,
        press: Iterable[str] = ("_",'_', '_', '_'),
        terminal_size: tuple[int, int] = (80, 24),
        run_before: Callable[[Pilot], Awaitable[None] | None] | None = None,
        args: Optional[List[str]] = None,
    ) -> bool:
        """Compare current snapshot with 'golden' example.

        Compare a current screenshot of the app running at app_path, with
        a previously accepted (validated by human) snapshot stored on disk.
        When the `--snapshot-update` flag is supplied (provided by syrupy),
        the snapshot on disk will be updated to match the current screenshot.

        Args:
            app_path (str):
                The path of the app. Relative paths are relative to the
                location of the test this function is called from.
            press (Iterable[str]):
                Key presses to run before taking screenshot. "_" is a short
                pause.
            terminal_size (tuple[int, int]):
                A pair of integers (WIDTH, HEIGHT), representing terminal size.
            run_before:
                An arbitrary callable that runs arbitrary code before taking
                the screenshot. Use this to simulate complex user interactions
                with the app that cannot be simulated by key presses.
        Returns:
            Whether the screenshot matches the snapshot.
        """
        args = args or []
        node = request.node
        path = Path(app_path)
        with temp_command_args(args):
            if path.is_absolute():
                # If the user supplies an absolute path, just use it directly.
                app = import_app(str(path.resolve()))
            else:
                # If a relative path is supplied by the user, it's relative to
                # the location of the pytest node, NOT the location that
                # `pytest` was invoked from.
                node_path = node.path.parent
                resolved = (node_path / app_path).resolve()
                app = import_app(str(resolved))

            actual_screenshot = take_svg_screenshot(
                app=app,
                press=press,
                terminal_size=terminal_size,
                run_before=run_before,
                app_path='/home/paul/np/sw/snippets/tests/runner.py',
            )

        result = snapshot == actual_screenshot
        if not result:
            # The split and join below is a mad hack, sorry...
            node.stash[TEXTUAL_SNAPSHOT_SVG_KEY] = "\n".join(
                str(snapshot).splitlines()[1:-1]
            )
            node.stash[TEXTUAL_ACTUAL_SVG_KEY] = actual_screenshot
            node.stash[TEXTUAL_APP_KEY] = app
        else:
            node.stash[TEXTUAL_SNAPSHOT_PASS] = True

        return result

    return compare


@dataclass
class SvgSnapshotDiff:
    """Model representing a diff between current and 'golden' screenshot.

    The current and actual snapshots are stored on disk. This is ultimately
    intended to be used in a Jinja2 template.
    """

    snapshot: Optional[str]
    actual: Optional[str]
    test_name: str
    path: PathLike
    line_number: int
    app: App
    environment: dict


def pytest_sessionfinish(
    session: Session,
    exitstatus: Union[int, ExitCode],
) -> None:
    """Perform post run processing.

    after whole test run finished, right before returning the exit status to
    the system. Generates the snapshot report and writes it to disk.
    """
    diffs: List[SvgSnapshotDiff] = []
    pass_count = 0
    for item in session.items:
        # Grab the data our fixture attached to the pytest node
        pass_count += int(
            item.stash.get(TEXTUAL_SNAPSHOT_PASS, False))
        snapshot_svg = item.stash.get(TEXTUAL_SNAPSHOT_SVG_KEY, None)
        actual_svg = item.stash.get(TEXTUAL_ACTUAL_SVG_KEY, None)
        app = item.stash.get(TEXTUAL_APP_KEY, None)

        if app:
            path, line_index, name = item.reportinfo()
            diffs.append(
                SvgSnapshotDiff(
                    snapshot=str(snapshot_svg),
                    actual=str(actual_svg),
                    test_name=name,
                    path=path,
                    line_number=line_index + 1,
                    app=app,
                    environment=dict(os.environ),
                )
            )

    if diffs:
        diff_sort_key = attrgetter("test_name")
        diffs = sorted(diffs, key=diff_sort_key)

        conftest_path = Path(__file__)
        snapshot_template_path = (
            conftest_path.parent / "snapshot_report_template.jinja2"
        )
        report_path_dir = conftest_path.parent / "output"
        report_path_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_path_dir / "snapshot_report.html"

        template = Template(snapshot_template_path.read_text())

        num_fails = len(diffs)
        num_snapshot_tests = len(diffs) + pass_count

        rendered_report = template.render(
            diffs=diffs,
            passes=pass_count,
            fails=num_fails,
            pass_percentage=100 * (pass_count / max(num_snapshot_tests, 1)),
            fail_percentage=100 * (num_fails / max(num_snapshot_tests, 1)),
            num_snapshot_tests=num_snapshot_tests,
            now=datetime.utcnow(),
        )
        with open(report_path, "w+", encoding="utf-8") as snapshot_file:
            snapshot_file.write(rendered_report)

        session.config._textual_snapshots = diffs
        session.config._textual_snapshot_html_report = report_path


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
        console.print(f'[bold]{snapshot_report_location}\n')
