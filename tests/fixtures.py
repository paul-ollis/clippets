"""Common test fixtures."""

import os
from dataclasses import dataclass
from datetime import datetime
from operator import attrgetter
from os import PathLike
from tempfile import NamedTemporaryFile
from pathlib import Path

from jinja2 import Template
from textual.app import App

import pytest
from _pytest.config import ExitCode
from _pytest.main import Session

TEXTUAL_SNAPSHOT_SVG_KEY = pytest.StashKey[str]()
TEXTUAL_ACTUAL_SVG_KEY = pytest.StashKey[str]()
TEXTUAL_SNAPSHOT_PASS = pytest.StashKey[bool]()
TEXTUAL_APP_KEY = pytest.StashKey[App]()

class TempTestFile:
    """A temporary file for testing.

    The only difference is that the string representation is the file's current
    contents.
    """

    def __init__(self, *args, **kwargs):
        self._f = NamedTemporaryFile(*args, **kwargs)

    @property
    def name(self):
        """The name of the temporary file."""
        return self._f.name

    def write(self, *args, **kwargs):
        """Write to the file."""
        return self._f.write(*args, **kwargs)

    def read(self, *args, **kwargs):
        """Reaf from the file."""
        return self._f.read(*args, **kwargs)

    def flush(self):
        """Flush the file."""
        return self._f.flush()

    def close(self):
        """Close the file."""
        return self._f.close()

    def seek(self, *args, **kwargs):
        """Seek within the file."""
        return self._f.seek(*args, **kwargs)

    def __str__(self):
        self._f.seek(0)
        return self._f.read()


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


def check_svg(expect, actual, request, app) -> bool:
    """Check expected against actual SVG screenshot."""
    #@ actual = actual.replace('font-size: 20px;', 'font-size: 15px;')
    #@ actual = actual.replace('font-size: 18px;', 'font-size: 13px;')
    result = expect == actual
    node = request.node
    if not result:
        # The split and join below is a mad hack, sorry...
        node.stash[TEXTUAL_SNAPSHOT_SVG_KEY] = "\n".join(
            str(expect).splitlines()[1:-1]
        )
        node.stash[TEXTUAL_ACTUAL_SVG_KEY] = actual
        node.stash[TEXTUAL_APP_KEY] = app
    else:
        node.stash[TEXTUAL_SNAPSHOT_PASS] = True

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
    app: App
    environment: dict


def save_svg_diffs(session: Session, exitstatus: int | ExitCode):
    """Store SVG differences."""
    # pylint: disable=too-many-locals
    diffs: list[SvgSnapshotDiff] = []
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
