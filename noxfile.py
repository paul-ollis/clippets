"Nox configuration."""

import nox                                       # pylint: disable=import-error


@nox.session(python=['3.9', '3.10', '3.11'], reuse_venv=True)
def test(session):
    """Run test under Python 3.11."""
    session.install(
        'jinja2',
        'markdown',
        'markdown_strings',
        'pytest',
        'pytest-asyncio',
        'pytest-xdist',
        'rich',
        'syrupy',
        'textual',
    )
    session.install('-e', './pytest-rich')
    session.install('-e', '.')
    args = ['pytest', *session.posargs, '-n28', '-vv', '-x', 'tests']
    session.run(*args)


@nox.session(reuse_venv=True)
def release(session):
    """Generate a release."""
    session.install(
        'build',
        'markdown',
        'markdown_strings',
        'rich',
        'textual',
    )
    session.run('python', 'tools/pre-release-check.py')
    session.run('python', '-m', 'build')
