"""Common test fixtures."""

import os
import pickle
from dataclasses import dataclass
from datetime import datetime
from operator import attrgetter
from os import PathLike
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp

from jinja2 import Template
from rich.console import ConsoleDimensions

import pytest
from _pytest.fixtures import FixtureRequest
from _pytest.main import Session
from syrupy import SnapshotAssertion

from support import AppRunner, TempTestFile

from clippets import core, snippets

HERE = Path(__file__).parent


class MyTemporaryDirectory(TemporaryDirectory):
    """A version of TemporaryDirectory that survives forking.

    This version will not automatically clean up when the process exits.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, name=None):      # pylint: disable=super-init-not-called
        if name:
            self.name = name
        else:
            self.name = mkdtemp(None, None, None)

    def cleanup(self):
        """Clean up the temporry directory."""
        self._rmtree(self.name, ignore_errors=True)


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
    f.close()


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
def work_file() -> TempTestFile:
    """Provide a temporary work file during test execution."""
    yield from temp_file('work.txt', 'w+t')


@pytest.fixture
def snapshot_run(snapshot: SnapshotAssertion, request: FixtureRequest):
    """Provide a way to run the Clippets app and capture a snapshot."""
    async def run_app(
            infile: TempTestFile, actions: list, *, log=False,
            post_delay: float = 0.0):
        runner = AppRunner(infile, actions)
        if log:
            with runner.logf:
                svg, tb = await runner.run(post_delay=post_delay)
        else:
            svg, tb = await runner.run(post_delay=post_delay)
        if tb:
            print(''.join(tb))
        assert not tb
        with runner.logf:
            ret = runner, check_svg(snapshot, svg, request, runner.app)
            return ret

    return run_app


@pytest.fixture(autouse=True)
def clean_data(pytestconfig, monkeypatch):
    """Reset some application data.

    This ensures that snippet/widget IDs can be predicted.
    """
    snippets.reset_for_tests()
    core.reset_for_tests()


class TempTestFileSource:
    """Fixture helper that can provide multiple test files."""

    def __init__(self):
        self.test_files = []

    def close(self):
        """Close all the temporary test files."""
        for f in self.test_files:
            f.close()

    def __call__(self, mode='wt', suffix='.txt'):
        """Create and remember a temporary test file."""
        f = TempTestFile(suffix=suffix, mode=mode)
        self.test_files.append(f)
        return f


@pytest.fixture
def gen_tempfile():
    """Provide a temporary file during test execution."""
    source = TempTestFileSource()
    yield source
    source.close()


def node_to_report_path(node):
    """Generate a reoirt file name for a test node."""
    path, _, name = node.reportinfo()
    temp = Path(path.parent)
    base = []
    while temp != temp.parent and temp.name != 'tests':
        base.append(temp.name)
        temp = temp.parent
    parts = []
    if base:
        parts.append('_'.join(reversed(base)))
    parts.append(path.name.replace('.', '_'))
    parts.append(name.replace('[', '_').replace(']', '_'))
    return Path(tempdir.name) / '_'.join(parts)


def check_svg(expect, actual, request, app) -> bool:
    """Check expected against actual SVG screenshot."""
    result = expect == actual
    svg_text = ''
    expect_svg_text = ''
    console = app.console
    p_app = PseudoApp(PseudoConsole(console.legacy_windows, console.size))
    if not result:
        # The split and join below is a mad hack, sorry...
        expect_svg_text = '\n'.join(str(expect).splitlines()[1:-1])
        svg_text = actual

    full_path, line_number, name = request.node.reportinfo()
    data_path = node_to_report_path(request.node)
    data = (
        result, expect_svg_text, svg_text, p_app, full_path, line_number, name)
    data_path.write_bytes(pickle.dumps(data))
    return result


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


def _get_svg_diffs(session: Session):
    diffs: list[SvgSnapshotDiff] = []
    pass_count = 0
    for data_path in Path(tempdir.name).iterdir():
        (passed, expect_svg_text, svg_text, app, full_path, line_index, name
            ) = pickle.loads(data_path.read_bytes())
        pass_count += 1 if passed else 0
        if not passed:
            diffs.append(SvgSnapshotDiff(
                snapshot=str(expect_svg_text),
                actual=str(svg_text),
                test_name=name,
                path=full_path,
                line_number=line_index + 1,
                app=app,
                environment=dict(os.environ)))
    return diffs, pass_count


def save_svg_diffs(session: Session):
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
    tempdir = MyTemporaryDirectory(tempdir_name)
else:
    tempdir = MyTemporaryDirectory()
    os.environ['SNIPPET_TEST_TEMPDIR'] = tempdir.name
