"""Common test fixtures."""

import pytest

from tempfile import NamedTemporaryFile


class TestFile:
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


def temp_file(suffix: str, mode: str) -> TestFile:
    """Provide a temporary file during test execution.

    :suffix:
        Text appended to the end of the file name. Typically just the extension
        (for example '.txt').
    :mode:
        The file's mode.
    """
    f = TestFile(suffix=suffix, mode=mode)
    yield f
    f.close()


@pytest.fixture
def snippet_infile() -> TestFile:
    """Provide a temporary input file during test execution.

    This is the file that will be used for input by the code under test. The
    returned (open) temporary file is writable (not readable).
    """
    yield from temp_file('in.txt', 'w+t')


@pytest.fixture
def snippet_outfile() -> TestFile:
    """Provide a temporary output file during test execution.

    This is the file that will be used for output by the code under test. The
    returned (open) temporary file is readable (not writable).
    """
    yield from temp_file('in.txt', 'r+t')


class TestFileSource:
    """Fixture helper that can provide multiple test files."""

    def __init__(self):
        self.test_files = []

    def close(self):
        """Close all the temporary test files."""
        for f in self.test_files:
            f.close()

    def __call__(self, mode='wt', suffix='.txt'):
        """Create and remember a temporary test file."""
        f = TestFile(suffix=suffix, mode=mode)
        self.test_files.append(f)
        return f


@pytest.fixture
def gen_tempfile():
    """Provide a temporary file during test execution."""
    source = TestFileSource()
    yield source
    source.close()
