"""Common test fixtures.

Much of the snapshot code in here is 'borrowed' from Textual's test code.
"""
from __future__ import annotations

import functools
import os
import pickle
import re
import shutil
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from operator import attrgetter
from os import PathLike
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp

from jinja2 import Template
from rich.console import ConsoleDimensions
from textual.app import App

import pytest
from _pytest.fixtures import FixtureRequest
from _pytest.main import Session
from syrupy import SnapshotAssertion
from syrupy.extensions.single_file import (
    SingleFileSnapshotExtension, WriteMode)

from support import AppRunner, EditTempFile, TempTestFile

from clippets import colors, core, robot, snippets

HERE = Path(__file__).parent


class SVGImageExtension(SingleFileSnapshotExtension):
    _file_extension = "svg"
    _write_mode = WriteMode.TEXT


@pytest.fixture
def snapshot(snapshot):
    return snapshot.use_extension(SVGImageExtension)


@pytest.fixture
def clean_version():
    """Fixture for cleaning the version in an SVG file."""
    def clean(svg: str) -> str:
        svg = re.sub(
            r':version:\&\#160;[0-9.]+?<', r':version:&#160;M.m.p<', svg)
        return re.sub(
            r'terminal-\d{6,}-', r'terminal-', svg)

    return clean


def rename_styles(svg: str) -> str:
    """Rename style names to prevent clashes when combined in HTML report."""
    return re.sub(
        r'terminal-r(\d+)', r'terminal-rx\1', svg)


class MyTemporaryDirectory(TemporaryDirectory):
    """A version of TemporaryDirectory that survives forking.

    This version will not automatically clean up when the process exits.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, name=None):      # pylint: disable=super-init-not-called
        if name:
            self.name = name                                 # pragma: no cover
        else:
            self.name = mkdtemp(None, None, None)

    def cleanup(self):
        """Clean up the temporry directory."""
        shutil.rmtree(self.name, ignore_errors=True)


@dataclass
class PseudoConsole:
    """Something that looks enough like a Console to fill a Jinja2 template."""

    legacy_windows: bool
    size: ConsoleDimensions


@dataclass
class PseudoApp:
    """Something that looks enough like an App to fill a Jinja2 template."""

    console: PseudoConsole


def temp_file(suffix: str, mode: str) -> TempTestFile:
    """Provide a temporary file during test execution.

    :suffix:
        Text appended to the end of the file name. Typically just the extension
        (for example '.txt').
    :mode:
        The file's mode.
    """
    f = TempTestFile(suffix=suffix, mode=mode)
    yield f
    with suppress(FileNotFoundError):
        f.close()


def temp_edit_file(suffix: str, mode: str) -> EditTempFile:
    """Provide a temporary editor emulation file during test execution.

    :suffix:
        Text appended to the end of the file name. Typically just the extension
        (for example '.txt').
    :mode:
        The file's mode.
    """
    f = EditTempFile(suffix=suffix, mode=mode)
    os.environ['CLIPPETS_TEST_PATH'] = f.name
    yield f
    f.close()


@pytest.fixture(autouse=True)
def set_env():
    """Set up the environment for these tests."""
    os.environ['CLIPPETS_EDITOR'] = f'python {HERE / "edit_helper.py"}'


@pytest.fixture
def snippet_infile() -> TempTestFile:
    """Provide a temporary input file during test execution.

    This is the file that will be used for input by the code under test. The
    returned (open) temporary file is writable (not readable).
    """
    yield from temp_file('in.txt', 'w+t')


@pytest.fixture
def snippet_outfile() -> TempTestFile:
    """Provide a temporary output file during test execution.

    This is the file that will be used for output by the code under test. The
    returned (open) temporary file is readable (not writable).
    """
    yield from temp_file('in.txt', 'r+t')


@pytest.fixture
def edit_text_file() -> EditTempFile:
    """Provide a temporary work file during test execution."""
    yield from temp_edit_file('work.txt', 'w+t')


@pytest.fixture
def simple_run() -> bool:
    """Provide a way to run the Clippets app.

    :return:
        A tuple of the AppRunner and a bool that is true if the app exited.
    """
    async def run_app(                                          # noqa: PLR0913
            infile: TempTestFile, actions: list, *, log=False,
            test_mode: bool = True, options: list[str] | None = None,
            expect_exit: bool = False):
        args = [infile.name]
        runner = AppRunner(
            infile.name, actions, test_mode=test_mode, options=options,
            make_app=lambda args: core.Clippets(core.parse_args(args)))
        if log:
            with runner.logf:                                # pragma: no cover
                _, tb, exited = await runner.run()
        else:
            _, tb, exited = await runner.run()
        if tb:
            if not (exited and expect_exit):                 # pragma: no cover
                print(''.join(tb))
                assert not tb
        return runner, exited

    return run_app


@pytest.fixture
def snapshot_run(snapshot: SnapshotAssertion, request: FixtureRequest):
    """Provide a way to run the Clippets app and capture a snapshot."""
    async def run_app(                                          # noqa: PLR0913
            infile: TempTestFile, actions: list, *, log=False,
            test_mode: bool = True, options: list[str] | None = None,
            expect_exit: bool = False,
            clean: Callable[[str], str] = lambda s: s,
            control_editor: bool = False):
        args = [infile.name]
        runner = AppRunner(
            infile.name, actions, test_mode=test_mode, options=options,
            control_editor=control_editor,
            make_app=lambda args: core.Clippets(core.parse_args(args)))
        if log:
            with runner.logf:                                # pragma: no cover
                svg, tb, exited = await runner.run()
        else:
            svg, tb, exited = await runner.run()
        if tb:
            if not (exited and expect_exit):                 # pragma: no cover
                print(''.join(tb))
                print(f'>>>> {tb!r}')
                assert not tb
        result, expect_text = check_svg(
            snapshot, clean(svg), request, runner.app)
        return runner, result

    return run_app


@pytest.fixture
def snapshot_run_dyn(snapshot_run):      # pylint: disable=redefined-outer-name
    """Provide a way to run the Clippets app and capture a snapshot.

    This basically wraps snapshot_run to allow Clippets to run with its
    background population and resolver tasks active.
    """
    return functools.partial(snapshot_run, test_mode=False)


@pytest.fixture(autouse=True)
def clean_data(pytestconfig, monkeypatch):
    """Reset some application data.

    This ensures that snippet/widget IDs can be predicted.
    """
    snippets.reset_for_tests()
    core.reset_for_tests()
    colors.reset_for_tests()


def node_to_report_path(node):
    """Generate a reoirt file name for a test node."""
    path, _, name = node.reportinfo()
    temp = Path(path.parent)
    base = []
    while temp != temp.parent and temp.name != 'tests':      # pragma: no cover
        base.append(temp.name)
        temp = temp.parent
    parts = []
    if base:                                                 # pragma: no cover
        parts.append('_'.join(reversed(base)))
    parts.append(path.name.replace('.', '_'))
    parts.append(name.replace('[', '_').replace(']', '_'))
    return Path(tempdir.name) / '_'.join(parts)


def check_svg(
        expect: SnapshotAssertion, actual: str, request: FixtureRequest,
        app: App,
    ) -> bool:
    """Check expected against actual SVG screenshot."""
    result = expect == actual
    svg_text = ''
    expect_svg_text = ''
    console = app.console
    p_app = PseudoApp(PseudoConsole(console.legacy_windows, console.size))
    if not result:                                           # pragma: no cover
        expect_svg_text = str(expect)
        svg_text = actual

    full_path, line_number, name = request.node.reportinfo()
    data_path = node_to_report_path(request.node)
    data = (
        result, expect_svg_text, svg_text, p_app, full_path, line_number, name)
    data_path.write_bytes(pickle.dumps(data))
    return result, expect_svg_text


@dataclass
class SvgSnapshotDiff:
    """Model representing a diff between current and 'golden' screenshot.

    The current and actual snapshots are stored on disk. This is ultimately
    intended to be used in a Jinja2 template.
    """

    snapshot: str | None
    actual: str | None
    test_name: str
    path: PathLike
    line_number: int
    app: PseudoApp
    environment: dict


def _get_svg_diffs(session: Session):                        # pragma: no cover
    diffs: list[SvgSnapshotDiff] = []
    pass_count = 0
    for data_path in Path(tempdir.name).iterdir():
        (passed, expect_svg_text, svg_text, app, full_path, line_index, name
            ) = pickle.loads(data_path.read_bytes())
        pass_count += 1 if passed else 0
        if not passed:
            diffs.append(SvgSnapshotDiff(
                snapshot=str(expect_svg_text),
                actual=rename_styles(svg_text),
                test_name=name,
                path=full_path,
                line_number=line_index + 1,
                app=app,
                environment=dict(os.environ)))
    return diffs, pass_count


def save_svg_diffs(session: Session):                        # pragma: no cover
    """Store SVG differences."""
    diffs, pass_count = _get_svg_diffs(session)
    if diffs:
        diffs = sorted(diffs, key=attrgetter("test_name"))

        snapshot_template_path = HERE / "snapshot_report_template.jinja2"
        report_path_dir = HERE / "output"
        report_path_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_path_dir / "snapshot_report.html"

        template = Template(snapshot_template_path.read_text())

        num_snapshot_tests = len(diffs) + pass_count
        rendered_report = template.render(
            diffs=diffs,
            passes=pass_count,
            fails=len(diffs),
            pass_percentage=100 * (pass_count / max(num_snapshot_tests, 1)),
            fail_percentage=100 * (len(diffs) / max(num_snapshot_tests, 1)),
            num_snapshot_tests=num_snapshot_tests,
            now=datetime.utcnow(),
        )
        with open(report_path, "w+", encoding="utf-8") as snapshot_file:
            snapshot_file.write(rendered_report)

        session.config._textual_snapshots = diffs
        session.config._textual_snapshot_html_report = report_path


tempdir_name = os.environ.get('SNIPPET_TEST_TEMPDIR', '')
if tempdir_name:
    tempdir = MyTemporaryDirectory(tempdir_name)             # pragma: no cover
else:
    tempdir = MyTemporaryDirectory()
    os.environ['SNIPPET_TEST_TEMPDIR'] = tempdir.name
