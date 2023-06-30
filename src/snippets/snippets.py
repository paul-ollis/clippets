"""Data structure used to store the snippet text."""

import itertools
import re
import sys
import textwrap
import weakref
from pathlib import Path
from typing import List, Optional, Set

from markdown_strings import esc_format

from . import colors


class Element:
    """An element in a tree of groups and snippets."""

    id_source = itertools.count()

    def __init__(self, parent: 'Element', first_line: Optional[str] = None):
        self.parent = parent
        self._uid = f'{self.__class__.__name__.lower()}-{next(self.id_source)}'
        self.first_line = first_line
        self.source_lines = []

    def uid(self):
        """Derive a unique ID for this element."""
        return self._uid

    def depth(self):
        """Calculete the depth of this element within the snippet tree."""
        if self.parent:
            return self.parent.depth() + 1
        return 0

    def is_empty(self):
        """Detemine if this snippet is empty."""
        return len(self.source_lines) == 0

    def source_len(self):
        """Calculete the number of line in this snippet."""
        return len(self.source_lines)

    def walk(self):
        """Walk this sub-tree - NOP default implementation."""
        return []

    def full_repr(self, end='\n'):                               # noqa: ARG002
        """Format a simple representation of this element.

        This is intended for test support. The exact format may change between
        releases.
        """
        body = self.body_repr()
        spc = ' ' if body else ''
        return f'{self.__class__.__name__}:{spc}{body}'

    def body_repr(self):
        """Format a simple representation of this element's body.

        This is intended for test support. The exact format may change between
        releases.
        """
        return ''

    def file_text(self):
        """Generate the text that should be written to a file."""
        return ''

    def clean(self) -> Optional['Element']:
        """Clean the source lines.

        Tabs are expanded and whitespace is trimmed from the end of each line.
        """
        self.source_lines = [
            line.expandtabs().rstrip() for line in self.source_lines]
        return None


class TextualElement(Element):
    """An `Element` that holds text."""

    marker = None

    def add(self, line):
        """Add a line to this element."""
        self.source_lines.append(line)

    @property
    def text(self) -> str:
        """Build the plain text for this snippet."""
        return '\n'.join(self.source_lines)

    def as_lines(self):
        """Build the file content lines for this snippet."""
        lines = [f'  {self.marker}\n'] if self.marker else []
        lines.extend(f'{line}\n' for line in self.source_lines)
        return lines

    @property
    def body(self) -> str:
        """The text that forms the body of this element, suitably cleaned.

        The first line is discarded along with any trailing blanks lines.
        Tab characters are expanded and then common leading whitespace is
        removed from the remaining lines.
        """
        return textwrap.dedent('\n'.join(self.source_lines))

    def body_repr(self):
        """Format a simple representation of this element's body.

        This is intended for test support. The exact format may change between
        releases.
        """
        return f'{self.body!r}'

    def file_text(self):
        """Generate the text that should be written to a file."""
        s = [f'  {self.marker}']
        for line in self.source_lines:
            s.append(f'    {line}')
        text = '\n'.join(s)
        return text.rstrip() + '\n'


class PreservedText(TextualElement):
    """Input file text that is preserved, but non-functional.

    This includes:

    - Additional vertical space.
    = Comment blocks.
    """

    def file_text(self):
        """Generate the text that should be written to a file."""
        return '\n'.join(self.source_lines) + '\n'

    def clean(self) -> Optional['Element']:
        """Clean the source lines."""
        if self.first_line is not None:
            self.source_lines = [self.first_line,  *self.source_lines]
        return super().clean()


class Snippet(TextualElement):
    """A plain text snippet."""

    marker = '@text@'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._marked_lines = []

    @property
    def marked_lines(self):
        """The snippet's lines, with keywords marked up."""
        if not self._marked_lines:
            keywords = self.parent.keywords()
            self._marked_lines = []
            for line in self.body.splitlines():
                newline = line
                for w in keywords:
                    rep = f'\u2e24{colors.keyword_code(w)}{w}\u2e25'
                    newline = newline.replace(w, rep)
                self._marked_lines.append(newline)
        return self._marked_lines

    @property
    def marked_text(self):
        """The snippet's text, with keywords marked up."""
        lines = textwrap.dedent('\n'.join(self.marked_lines)).splitlines()
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines)

    def reset(self):
        """Clear any cached state."""
        self._marked_lines = []

    def md_lines(self):
        """Provide snippet lines in Markdown format.

        This escapes anything that looks like Markdown syntax.
        """
        return esc_format(self.body).splitlines()

    def duplicate(self):
        """Create a duplicate of this snippet."""
        inst = self.__class__(self.parent)
        inst.source_lines = list(self.source_lines)
        return inst

    def set_text(self, text):
        """Set the text for this snippet.

        This is only used when the source file is also updated. So the end line
        index is updated along with the source lines.
        """
        self._marked_lines = []
        self.source_lines = [f'   {line}' for line in text.splitlines()]
        if self.source_lines[-1].strip():
            self.source_lines.append('')

    def clean(self) -> Optional['Element']:
        """Clean the source lines.

        Tabs are expanded and whitespace is trimmed from the end of each line.
        Trailing blank lines are deleted and common leading white space
        removed.

        :return:
            Any trailing lines that were removed  are returned in a new
            `PreservedText` instance.
        """
        super().clean()
        lines = self.source_lines
        removed = []
        while lines and not lines[-1].strip():
            removed.append(lines.pop())
        self.source_lines[:] = textwrap.dedent('\n'.join(lines)).splitlines()
        if removed:
            p = PreservedText(parent=None)
            while removed:
                p.add(removed.pop())
            return p
        else:
            return None


class MarkdownSnippet(Snippet):
    """A snippet that is interpreted as Markdown text."""

    marker = '@md@'

    def md_lines(self):
        """Provide snippet lines in Markdown format.

        This simply provides unmodified lines.
        """
        return self.body.splitlines()


class KeywordSet(TextualElement):
    """An element holding a set of keywords."""

    marker = '@keywords@'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.words = set()

    def add(self, line):
        """Add a a line to this set of keywords.

        The line is split at spaces to obtain the set of keywords.
        """
        super().add(line)
        new_words = self.source_lines[-1].split()
        for w in new_words:
            colors.add_keyword(w)
        self.words.update(new_words)

    @property
    def text(self):
        """Build the plain text for this snippet."""
        return '\n'.join(sorted(self.words))

    def file_text(self) -> str:
        """Generate the text that should be written to a file."""
        s = [f'  {self.marker}']
        for line in self.text.splitlines():
            s.append(f'    {line}')
        text = '\n'.join(s)
        return text.rstrip() + '\n'

    def body_repr(self):
        """Format a simple representation of this element's body.

        This is intended for test support. The exact format may change between
        releases.
        """
        return f'{" ".join(sorted(self.words))}'

    @classmethod
    def combine(cls, *keyword_sets):
        """Combine multiple KeywordSet instances into just one."""
        words = set(itertools.chain(*[kws.words for kws in keyword_sets]))
        if words:
            first = keyword_sets[0]
            kws = cls(parent=first.parent)
            kws.words.update(words)
            return kws
        else:
            return None


class Title(TextualElement):
    """A simple, one-line, title for a tree of snippets."""

    marker = '@title:'


class Group(Element):
    """A group of sniipets and/or sub groups."""

    all_tags = set()

    def __init__(self, name, parent=None, tag_text=''):
        super().__init__(parent)
        self.name = name
        self.groups = {}
        tags = {t.strip() for t in tag_text.split()}
        self.tags = sorted(tags)
        for t in self.tags:
            self.all_tags.add(t)
        self.children = [KeywordSet(parent=self)]

    def add_group(self, name):
        """Add a new group as a child of this group."""
        name, _, rem = name.partition('[')
        tag_text, *_ = rem.partition(']')
        name = name.strip()

        if name not in self.groups:
            if self.tags:
                tag_text = ' '.join(self.tags) + ' ' + tag_text
            self.groups[name] = Group(
                name, weakref.proxy(self), tag_text=tag_text)
        return self.groups[name]

    def add(self, child):
        """Add a new element as a child of this group."""
        self.children.append(child)

    def clean(self):
        """Clean up this and any shild groups.

        Empty children and groups are removed.
        """
        self.children[:] = [c for c in self.children if not c.is_empty()]
        for group in self.groups.values():
            group.clean()
        for child in self.children:
            child.clean()
        keyword_sets = {c for c in self.children if isinstance(c, KeywordSet)}
        self.children = [c for c in self.children if c not in keyword_sets]
        kws = KeywordSet.combine(*keyword_sets)
        if kws:
            self.children[0:0] = [kws]

    def is_empty(self):
        """Test whether this group has zero children."""
        return bool(self.children)

    def snippets(self) -> List[Snippet]:
        """Provide this group's snippets."""
        return [c for c in self.children if isinstance(c, Snippet)]

    def walk(self, predicate=lambda _el: True):
        """Iterate over the entire tree of groups and snippets.

        Immediate child snippets are visited before sub-groups.
        """
        yield from (c for c in self.children if predicate(c))
        for group in self.groups.values():
            if predicate(group):
                yield group
            yield from group.walk(predicate)

    def walk_snippets(self):
        """Iterate over all snippets, breadth first."""
        def is_textual(el):
            return isinstance(el, Snippet)

        yield from self.walk(predicate=is_textual)

    def walk_groups(self, predicate=lambda _el: True):
        """Iterate over all groups."""
        for g in self.walk(predicate=lambda el: isinstance(el, Group)):
            if predicate(g):
                yield g

    def first_snippet(self) -> Optional[Snippet]:
        """Get the first snippit, if any."""
        try:
            return next(self.walk_snippets())
        except StopIteration:
            return None

    def find_element_by_uid(self, uid) -> Optional[Element]:
        """Find an element with the given UID."""
        for el in self.walk():
            if el.uid() == uid:
                return el
        return None

    def find_snippet_before_id(self, uid):
        """Find the snippet before the one with the given UID."""
        def is_textual(el):
            return isinstance(el, Snippet)

        prev = None
        for el in self.walk():
            if is_textual(el):
                if el.uid() == uid:
                    return prev
                else:
                    prev = el
        return None

    def find_snippet_after_id(self, uid):
        """Find the snippet after the one with the given UID."""
        def is_textual(el):
            return isinstance(el, Snippet)

        prev = None
        for el in self.walk():
            if is_textual(el):
                if prev and prev.uid() == uid:
                    return el
                else:
                    prev = el
        return None

    def iter_from_to(self, first, second):
        """Iterate iver a subset of elements."""
        def is_textual(el):
            return isinstance(el, Snippet)

        in_range = False
        for el in self.walk():
            if is_textual(el):
                if in_range:
                    yield el
                if el.uid() == first:
                    in_range = True
                    yield el
            if el.uid() == second:
                break

    def correctly_ordered(self, first, second):
        """Test whether first is after second."""
        for el in self.walk():
            if el.uid() == first:
                return True
            elif el.uid() == second:
                return False
        return False

    def keyword_set(self) -> Optional[KeywordSet]:
        """Find the keyword set, if any, for this group."""
        return self.children[0]

    def keywords(self) -> Set[str]:
        """Provide all the keywords applicable to this group's snippets."""
        return self.keyword_set().words

    def outline_repr(self, end='\n'):
        """Format a simple group-only outline representation of the tree.

        This is intended for test support. The exact format may change between
        releases.
        """
        s = [self.name]
        for g in self.groups.values():
            s.append(g.outline_repr(end=''))
        return '\n'.join(s) + end

    def full_repr(self, end='\n'):
        """Format a simple outline representation of the tree.

        This is intended for test support. The exact format may change between
        releases.
        """
        s = [f'Group: {self.name}']
        for c in self.children:
            s.append(c.full_repr(end=''))
        for g in self.groups.values():
            s.append(g.full_repr(end=''))
        return '\n'.join(s) + end

    def file_text(self):
        """Generate the text that should be written to a file."""
        return f'{self.name}\n'


class Loader:
    """Encapsulation of snippet loading machinery."""

    def __init__(self, path):
        self.path = path
        self.el: Element = PreservedText(parent=None)
        self.root = self.cur_group = Group('<ROOT>')
        self.title = ''

    def store(self):
        """Store the current element if not empty."""
        el = self.el
        preserved_text = el.clean()
        if not el.is_empty():
            self.cur_group.add(el)
        if preserved_text:
            self.cur_group.add(preserved_text)
        self.el = PreservedText(parent=None)

    def handle_comment(self, line):
        """Handle a comment line."""
        if line.startswith('#'):
            if not isinstance(self.el, PreservedText):
                self.store()
                self.el = PreservedText(parent=None)
            self.el.add(line)
            return True
        else:
            return False

    def handle_title(self, line):
        """Handle a title line."""
        if line.startswith('@title:'):
            self.store()
            self.cur_group.add(Title(parent=self.cur_group))
            self.el = PreservedText(parent=None)
            return True
        else:
            return False

    def handle_group(self, line):
        """Handle a group start line."""
        r_group = re.compile(r'([^ ].*)')
        m = r_group.match(line)
        if m:
            self.store()
            text = m.group()
            sub_groups = [g.strip() for g in text.split(':')]
            self.cur_group = self.root.add_group(sub_groups.pop(0))
            while sub_groups:
                self.cur_group = self.cur_group.add_group(sub_groups.pop(0))
            self.el = PreservedText(parent=None)
            return True
        else:
            return False

    def handle_marker(self, line):
        """Handle a marker line."""
        r_marker = re.compile(r'^ +?@(.*)@ *$')
        m = r_marker.match(line)
        if m:
            self.store()
            if m.group(1) == 'keywords':
                self.el = KeywordSet(parent=self.cur_group)
            elif m.group(1) == 'md':
                self.el = MarkdownSnippet(parent=self.cur_group)
            else:
                self.el = Snippet(parent=self.cur_group)
            return True
        else:
            return False

    def load(self):
        """Load a tree of snippets from a file."""
        with Path(self.path).open(mode='rt') as f:
            self.el = PreservedText(parent=None)
            for rawline in f:
                line = rawline.rstrip()
                if not (self.handle_comment(line)
                        or self.handle_title(line)
                        or self.handle_group(line)
                        or self.handle_marker(line)):
                    self.el.add(line)

        self.store()
        self.root.clean()
        if not self.root.groups:
            sys.exit(f'File {self.path} contains no groups')

        for el in self.root.walk_snippets():
            el.reset()
        return self.root, self.title


def id_of_element(obj: Optional[Element]) -> Optional[str]:
    """Get the unique ID of an Element."""
    return None if obj is None else obj.uid()


def load(path):
    """Load a tree of snippets from a file."""
    loader = Loader(path)
    return loader.load()


def save(path, root):
    """Save a snippet tree to a file."""
    with Path(path).open('wt') as f:
        for el in root.walk():
            f.write(el.file_text())
