"""Script to perform a pre-relase check."""

import subprocess
import sys
from functools import partial
from pathlib import Path

run = partial(subprocess.run, capture_output=True, text=True)


def check_git_is_clean():
    """Check the the working tree is clean."""
    unstaged = run(['git', 'diff', '--quiet'])
    if unstaged.returncode:
        sys.exit('You have unstaged changes.')

    staged = run(['git', 'diff', '--quiet', '--cached'])
    if staged.returncode:
        sys.exit('You have staged changes.')


def check_version():
    """Check that version information matches and is correct."""
    pyproject = Path('pyproject.toml')
    help_text = Path('src/clippets/help.txt')
    pyproject_version = help_version = ''
    for line in pyproject.read_text().splitlines():
        if line.startswith('version = "'):
            _, _, rem = line.partition('"')
            pyproject_version, *_ = rem.partition('"')
            break
    for line in help_text.read_text().splitlines():
        if line.startswith(':version: '):
            *_, help_version = line.rpartition(':')
            help_version = help_version.strip()
            break
    if not pyproject_version:
        sys.exit(f'Could not find version in {pyproject}')
    if not help_version:
        sys.exit(f'Could not find version in {help_text}')
    if pyproject_version != help_version:
        sys.exit(f'Versions to not match in {pyproject} and {help_text}')

    version_tag = f'v{pyproject_version}'
    tags_text = run(['git', 'show-ref', '--tags']).stdout.splitlines()
    tag_tuples = [line.rpartition('/') for line in tags_text]
    tags = {c: a.split()[0] for a, b, c in tag_tuples}
    if version_tag not in tags:
        sys.exit(f'There is no tag for version {pyproject_version}')

    head = run(['git', 'rev-parse', 'HEAD']).stdout.strip()
    if head != tags[version_tag]:
        sys.exit(f'HEAD does not match tags for {pyproject_version}')


check_git_is_clean()
check_version()
