"""Data structure used to store the snippet text."""
# pylint: disable=too-many-lines
from __future__ import annotations

import asyncio
import itertools
import re
import shutil
import sys
import textwrap
import weakref
from contextlib import suppress
from functools import partial
from io import StringIO
from pathlib import Path
from typing import (
    Callable, ClassVar, Iterable, Literal, Sequence, TypeAlias, cast)

from markdown_strings import esc_format

from . import colors
from .text import render_text


class SnippetInsertionPointer:
    """A 'pointer' of where to insert a snippet within a snippet tree.

    An insertion point can be before or after a snippet. Within a group, an
    insertion point below one snippet is equal to an insertion point above the
    following snippet.
    """

    def __init__(self, snippet: Snippet):
        self._snippet = snippet
        self.after = False
        self._prev_snippet: bool | None | Snippet = False
        self._next_snippet: bool | None | Snippet = False

    @property
    def snippet(self):
        """The snippet part of this pointer."""
        return self._snippet

    @snippet.setter
    def snippet(self, value):
        self._snippet = value
        self._prev_snippet = False
        self._next_snippet = False

    @property
    def prev_snippet(self):
        """The previous snippet within this snippet's group."""
        if self._prev_snippet is False:
            self._prev_snippet = self.snippet.neighbour(
                backwards=True, within_group=True, predicate=is_snippet_like)
        return self._prev_snippet

    @property
    def next_snippet(self):
        """The next snippet within this snippet's group."""
        if self._next_snippet is False:
            self._next_snippet = self.snippet.neighbour(
                within_group=True, predicate=is_snippet_like)
        return self._next_snippet

    @property
    def addr(self) -> tuple[str, bool]:
        """The insertaion point in the form (uid, insert_after)."""
        return self.snippet.uid(), self.after

    def move(self, *, skip: Snippet, backwards: bool = False) -> bool:
        """Move to the next insertion point.

        :return:
            True if movement occurred.
        """
        def do_move():
            snippet = self.snippet
            if backwards:
                if self.after:
                    self.after = False
                    return
            elif not self.after and snippet.is_last():
                self.after = True
                return
            new_snippet = snippet.neighbour(
                backwards=backwards, within_group=False,
                predicate=is_snippet_like)
            if new_snippet:
                self.snippet = new_snippet
                if isinstance(new_snippet, PlaceHolder):
                    self.after = False
                elif new_snippet.is_last():
                    self.after = backwards
                else:
                    self.after = False

        saved = self.snippet, self.after
        addr = self.addr
        for _ in range(3):
            do_move()
            if addr != self.addr and not self.is_next_to(skip):
                return True

        self.snippet, self.after = saved
        return False

    def is_next_to(self, snippet: Snippet) -> bool:
        """Test if a this pointer is adjacent to a snippet."""
        if self.snippet.parent is not snippet.parent:
            return False
        elif self.snippet is snippet:
            return True
        elif self.prev_snippet is snippet:
            return not self.after
        elif self.next_snippet is snippet:
            return self.after
        else:
            return False

    def move_snippet(self, snippet) -> bool:
        """Move a given snippet to this insertion point."""
        if self.is_next_to(snippet):
            return False                                     # pragma: no cover
        snippet.parent.remove(snippet)
        snippet.parent.clean()
        if self.after:
            self.snippet.parent.add(snippet, after=self.snippet)
        else:
            self.snippet.parent.add(snippet, before=self.snippet)
        self.snippet.parent.clean()
        return True

    def __repr__(self):
        return f'Pointer({self.snippet.uid()}, {self.after})'


class Element:
    """An element in a tree of groups and snippets.

    Many subclasses of Element provide a unique ID, available using a ``uid``
    method. Such UIDs follow a simple naming convention, which other parts of
    the Clippet's code relies on. Snippet instances have UIDs of
    the form <snippet>-<n>, for example, 'snippet-6'. The important ID forms
    are:

    snippet-<n>
        A simple (text) `Snippet` or a `MarkdownSnippet`.
    group-<n>
        A snippet `Group`.
    """

    id_source = itertools.count()
    has_uid: bool = True

    def __init__(self, parent: Group):
        self.parent: Group = parent
        if self.has_uid:
            n = next(self.id_source)
            self._uid = f'{self._uid_base_name()}-{n}'
        else:
            self._uid = ''
        self._source_lines: list[str] = []
        self.dirty = True

    @property
    def source_lines(self) -> Sequence[str]:
        """The source lines for this element."""
        return tuple(self._source_lines)

    @source_lines.setter
    def source_lines(self, value: Iterable[str]):
        self._source_lines = list(value)
        self.dirty = True

    @property
    def root(self):
        """The root group of the tree containing this element."""
        return self.parent.root

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

    def full_repr(self, *, end='\n', debug: bool = False):
        """Format a simple representation of this element.

        This is intended for test support. The exact format may change between
        releases.
        """
        body = self.body_repr()
        spc = ' ' if body else ''
        id_part = f' {self.uid()}' if debug else ''
        return f'{self.__class__.__name__}{id_part}:{spc}{body}'

    def body_repr(self):                          # pylint: disable=no-self-use
        """Format a simple representation of this element's body.

        This is intended for test support. The exact format may change between
        releases.
        """
        return ''                                            # pragma: no cover

    def file_text(self):                          # pylint: disable=no-self-use
        """Generate the text that should be written to a file."""
        return ''

    def clean(self) -> Element | None:                   # type: ignore[return]
        """Clean the source lines.

        Tabs are expanded and whitespace is trimmed from the end of each line.
        """
        self.source_lines = [
            line.expandtabs().rstrip() for line in self.source_lines]

    def neighbour(
            self, *,
            backwards: bool = False,
            within_group: bool = False,
            predicate=lambda _el: True) -> Snippet | None:
        """Get this element's immediate neighbour.

        :backwards:    If set then find preceding neighbour.
        :within_group: If set then do not check neighbouring groups.
        :predicate:    Funciton to test whether a given element should be
                       considered a neighbour.
        """
        snippets = self.root.walk(
            predicate=predicate, first_id=self.uid(), backwards=backwards)
        for i, snippet in enumerate(snippets):
            if i == 1:
                if within_group and snippet.parent is not self.parent:
                    return None
                else:
                    return snippet
        return None

    @classmethod
    def _uid_base_name(cls):
        return cls.__name__.lower()


class PlaceHolder(Element):
    """A place holder used in empty groups."""

    id_source = itertools.count()

    @staticmethod
    def is_last() -> bool:
        """Return false."""
        return False                                         # pragma: no cover


class TextualElement(Element):
    """An `Element` that holds text."""

    id_source = itertools.count()
    marker:str = ''

    def add(self, line):
        """Add a line to this element."""
        self._source_lines.append(line)

    @property
    def text(self) -> str:
        """Build the plain text for this snippet."""
        return '\n'.join(self.source_lines)

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

    id_source = itertools.count()
    has_uid: bool = False

    def file_text(self):
        """Generate the text that should be written to a file."""
        return '\n'.join(self.source_lines) + '\n'


class Snippet(TextualElement):
    """A plain text snippet."""

    id_source = itertools.count()
    marker = '@text@'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._marked_lines = []

    @property
    def marked_lines(self):
        """The snippet's lines, with keywords marked up."""
        keywords = self.parent.keywords()
        if not self._marked_lines:
            if keywords:
                ored_words = '|'.join(keywords)
                expr = rf'\b({ored_words})\b'
                r_words = re.compile(expr)
                self._marked_lines = []
                for line in self.body.splitlines():
                    parts = r_words.split(line)
                    new_parts = []
                    for i, part in enumerate(parts):
                        if i & 1:
                            code = colors.keywords.code(part)
                            rep = f'\u2e24{code}{part}\u2e25'
                            new_parts.append(rep)
                        else:
                            new_parts.append(part)
                    self._marked_lines.append(''.join(new_parts))
            else:
                self._marked_lines = self.body.splitlines()
        return self._marked_lines

    @property
    def marked_text(self):
        """The snippet's text, with keywords marked up."""
        lines = textwrap.dedent('\n'.join(self.marked_lines)).splitlines()
        return render_text('\n'.join(lines))

    def reset(self):
        """Clear any cached state."""
        self._marked_lines = []
        self.dirty = True

    def is_last(self) -> bool:
        """Test if a snippet is the last in its group."""
        return self.parent.is_last_snippet(self)

    def md_lines(self):
        """Provide snippet lines in Markdown format.

        This escapes anything that looks like Markdown syntax.
        """
        return esc_format(self.body).splitlines()

    def add_new(self) -> Snippet:
        """Add a new snippet, inserted after this one."""
        inst = self.__class__(self.parent)
        self.parent.add(inst, after=self)
        return inst

    def duplicate(self) -> Snippet:
        """Create a duplicate of this snippet, inserted after."""
        inst = self.__class__(self.parent)
        inst.source_lines = list(self.source_lines)
        self.parent.add(inst, after=self)
        return inst

    def set_text(self, text):
        """Set the text for this snippet."""
        self._marked_lines = []
        self.source_lines = text.splitlines()

    def clean(self) -> Element | None:
        """Clean the source lines.

        Tabs are expanded and whitespace is trimmed from the end of each line.
        Trailing blank lines are deleted and common leading white space
        removed.

        :return:
            Any trailing lines that were removed  are returned in a new
            `PreservedText` instance.
        """
        super().clean()
        lines = self._source_lines
        removed = []
        while lines and not lines[-1].strip():
            removed.append(lines.pop())
        self._source_lines[:] = textwrap.dedent('\n'.join(lines)).splitlines()
        if removed:
            p = PreservedText(parent=self.parent)
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

    @property
    def marked_text(self):
        """The snippet's text, with keywords marked up."""
        lines = textwrap.dedent('\n'.join(self.marked_lines)).splitlines()
        return '\n'.join(lines)

    @classmethod
    def _uid_base_name(cls):
        return 'snippet'


class KeywordSet(TextualElement):
    """An element holding a set of keywords."""

    id_source = itertools.count()
    marker = '@keywords@'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.words = set()

    def add(self, line):
        """Add a entry to this set of keywords.

        The line is split at spaces to obtain the set of keywords.
        """
        super().add(line)
        new_words = self.source_lines[-1].split()
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

    def is_empty(self):
        """Detemine if this keyword set is empty."""
        return not self.words

    @classmethod
    def combine(cls, parent, *keyword_sets):
        """Combine multiple KeywordSet instances into just one."""
        words = set(itertools.chain(*[kws.words for kws in keyword_sets]))
        kws = cls(parent=parent)
        if words:
            kws.words.update(words)
        return kws


class Title(TextualElement):
    """A simple, one-line, title for a tree of snippets."""

    marker = '@title:'


class GroupDebugMixin:
    """Support for test and debug of the `Group`` class."""

    uid: Callable[[], str]
    name: str
    groups: dict[str, Group]
    children: list[Element]
    parent: Group
    ordered_groups: list[Group]

    def outline_repr(self, end='\n'):
        """Format a simple group-only outline representation of the tree.

        This is intended for test support. The exact format may change between
        releases.
        """
        s = [self.name]
        for g in self.ordered_groups:
            s.append(g.outline_repr(end=''))
        return '\n'.join(s) + end

    @property
    def repr_full_name(self):
        """The full repr name of this group."""
        if self.parent and self.parent.parent:
            pfull_name = self.parent.repr_full_name if self.parent else ''
        else:
            pfull_name = ''
        if pfull_name:
            return f'{pfull_name}:{self.name}'
        else:
            return self.name

    def full_repr(self, end='\n', *, debug: bool = False):
        """Format a simple outline representation of the tree.

        This is intended for test support. The exact format may change between
        releases.
        """
        if debug:                                            # pragma: no cover
            s = [f'Group: {self.repr_full_name} {self.uid()}']
        else:
            s = [f'Group: {self.repr_full_name}']
        for c in self.children:
            if not isinstance(c, PlaceHolder):
                s.append(c.full_repr(end='', debug=debug))
        for g in self.ordered_groups:
            s.append(g.full_repr(end='', debug=debug))
        return '\n'.join(s) + end


class Group(GroupDebugMixin, Element):
    """A group of snippets and/or sub groups."""

    # pylint: disable=too-many-public-methods
    id_source = itertools.count()
    all_tags: ClassVar[set[str]] = set()

    def __init__(self, name, parent=None, tag_text=''):
        super().__init__(parent)
        self.name = name
        self.title = ''
        self.groups: dict[str, Group] = {}
        self._ordered_groups: list[str] = []
        tags = {t.strip() for t in tag_text.split()}
        self.tags = sorted(tags)
        for t in self.tags:
            self.all_tags.add(t)
        self.children = [KeywordSet(parent=self)]

    @property
    def ordered_groups(self):
        """The groups in user-defined order."""
        return [self.groups[name] for name in self._ordered_groups]

    def rename(self, name):
        """Change the name of this group."""
        self.parent.rename_child_group(self.name, name)
        self.name = name

    def rename_child_group(self, old_name: str, new_name: str):
        """Update to reflect a name change for a child group."""
        idx = self._ordered_groups.index(old_name)
        self._ordered_groups[idx] = new_name
        self.groups[new_name] = self.groups.pop(old_name)

    def add_group(self, name, after: str = ''):
        """Add a new group as a child of this group.

        :after:
            If set then the new group is added after the group with this name.
        """
        name, _, rem = name.partition('[')
        tag_text, *_ = rem.partition(']')
        name = name.strip()

        if name not in self.groups:
            if self.tags:
                tag_text = ' '.join(self.tags) + ' ' + tag_text
            self.groups[name] = Group(
                name, weakref.proxy(self), tag_text=tag_text)
            if after:
                i = self._ordered_groups.index(after)
                self._ordered_groups[i + 1:i + 1] = [name]
            else:
                self._ordered_groups.append(name)
        return self.groups[name]

    def add(
            self, child,
            after: Element | Literal[0] | None = None,
            before: Element | None = None):
        """Add a new element as a child of this group."""
        children = self.children
        if after == 0:
            p = 1
        elif after:
            p = children.index(after) + 1
        elif before:
            p = children.index(before)
        else:
            p = len(children)
        self.children[p:p] = [child]
        child.parent = self

    def add_new(self):
        """Add a new snippet at the start of this group."""
        snippet = MarkdownSnippet(parent=self)
        self.add(snippet, after=0)
        return snippet

    def remove(self, child):
        """Remove a child element from this group."""
        with suppress(ValueError):
            self.children.remove(child)
        snippets = [el for el in self.children if isinstance(el, Snippet)]
        if not snippets:
            self.children.append(PlaceHolder(parent=self))

    def clean(self) -> Element | None:                   # type: ignore[return]
        """Clean up this and any child groups.

        Empty children and groups are removed and a place-holder added if
        necessary.
        """
        self.children[:] = [c for c in self.children if not c.is_empty()]
        for group in self.ordered_groups:
            group.clean()
        for child in self.children:
            child.clean()
        keyword_sets = {c for c in self.children if isinstance(c, KeywordSet)}
        self.children = [c for c in self.children if c not in keyword_sets]
        kws = KeywordSet.combine(self, *keyword_sets)
        self.children[0:0] = [kws]

        if self.parent:
            snippets = [el for el in self.children if isinstance(el, Snippet)]
            if not snippets:
                self.children.append(PlaceHolder(parent=self))

    def basic_walk(self, *, backwards: bool = False):
        """Iterate over the entire tree of groups and snippets.

        :backwards:
            If set the walk in reverse order; i.e. last snippt is visited
            first.
        """
        if backwards:
            for group in reversed(self.ordered_groups):
                yield from group.basic_walk(backwards=backwards)
                yield group
            yield from reversed(self.children[1:])
        else:
            yield from self.children[1:]
            for group in self.ordered_groups:
                yield group
                yield from group.basic_walk(backwards=backwards)

    @property
    def root(self):
        """The root group of the tree containin this group."""
        if self.parent is None:
            return self
        return self.parent.root

    def snippets(self):
        """Iterate over all child snippets."""
        yield from (el for el in self.children[1:] if isinstance(el, Snippet))

    def step_group(self, *, backwards: bool = False) -> Group | None:
        """Get the group before or after this onw."""
        for el in self.root.walk(
                predicate=is_group, after_id=self.uid(), backwards=backwards):
            return el
        return None

    def is_last_snippet(self, snippet: Snippet) -> bool:
        """Test if a snippet is the last in this gruop."""
        snippets = [el for el in self.children if isinstance(el, Snippet)]
        return bool(snippets) and snippets[-1] is snippet

    def keyword_set(self) -> KeywordSet:
        """Find the keyword set, for this group."""
        return cast(KeywordSet, self.children[0])

    def keywords(self) -> set[str]:
        """Provide all the keywords applicable to this group's snippets."""
        return self.keyword_set().words

    @property
    def full_name(self):
        """The full name of this group."""
        pfull_name = self.parent.full_name if self.parent else ''
        if pfull_name:
            return f'{pfull_name} : {self.name}'
        elif self.name != '<ROOT>':
            return self.name
        else:
            return ''

    def file_text(self):
        """Generate the text that should be written to a file."""
        if self.tags:
            return f'{self.full_name} [{" ".join(self.tags)}]\n'
        else:
            return f'{self.full_name}\n'


class Root(Group):
    """A group that acts as  the root of the snippet tree."""

    def reset(self):
        """Reset to initialised state.

        This is used prior to a complete relead.
        """
        self.groups = {}
        self._ordered_groups = []

    def walk(
            self, predicate=lambda _el: True, *, first_id: str | None = None,
            after_id: str | None = None, backwards: bool = False):
        """Iterate over the entire tree of groups and snippets.

        :predicate:
            A function  taking an 'Element' as it only argument. Only elements
            for which this returns a true value are visited.
        :first_id:
            If not an empty string, Skip all elements before the one with this
            ID.
        :after_id:
            If not an empty string, Skip all elements upto and including
            the one with this ID. This and the `first_id` argument are mutually
            exclusive
        :backwards:
            If set the walk in reverse order; i.e. last snippt is visited
            first.
        """
        yield from walk_group_tree(
            partial(self.basic_walk, backwards=backwards),
            predicate=predicate, first_id=first_id, after_id=after_id)

    def find_element_by_uid(self, uid) -> Element | None:
        """Find an element with the given UID."""
        for el in self.walk():
            if el.uid() == uid:
                return el
        return None

    def first_snippet(self) -> Snippet | None:
        """Get the first snippet, if any."""
        for el in self.walk(predicate=is_snippet):
            return el
        return None

    def first_group(self) -> Group:
        """Get the first group.

        :return:
            The first group. Note that the Root always has at least on e group
            so, in practice, this cannot return itself.
        """
        for group in self.ordered_groups:
            return group
        return self                                          # pragma: no cover

    def update_keywords(self):
        """Update the keyword tracker with any changes."""
        all_keywords: set[str] = set()
        for group in self.walk(is_group):
            all_keywords |= group.keywords()
        colors.keywords.apply_changes(all_keywords)


def walk_group_tree(
        basic_walk, predicate=lambda _el: True, first_id: str | None = None,
        after_id: str | None = None):
    """Perform a walk."""
    it = basic_walk()
    if first_id or after_id:
        for el in it:
            if el.uid() == after_id:
                break
            if el.uid() == first_id:
                if predicate(el):
                    yield el
                break
    for el in it:
        if predicate(el):
            yield el


ParsedElement: TypeAlias = PreservedText | Snippet | KeywordSet


class Loader:                    # pylint: disable=too-many-instance-attributes
    """Encapsulation of snippet loading machinery."""

    def __init__(self, path: str, *, root: Root | None = None):
        self.path = Path(path)
        self.root = root or Root('<ROOT>')
        self.el: ParsedElement = Snippet(parent=self.root)
        self.cur_group: Group = Group('')
        self.monitor_task: asyncio.Task | None = None
        self.load_time: float = 0.0
        self.stop_event = asyncio.Event()

    def start_monitoring(self, on_change_callback: Callable):
        """Start a task that monitors for change to the loaded file."""
        self.monitor_task = asyncio.create_task(
            self.monitor(on_change_callback), name='monitor_file')

    async def stop_monitoring(self):
        """Stop monitoring for changes to the loaded file."""
        if self.monitor_task:
            self.stop_event.set()
            await self.monitor_task

    async def monitor(self, on_change_callback: Callable):
        """Task that monitors for changes to the loaded file."""
        async def pause(delay) -> bool:
            await asyncio.wait([stop_waiter], timeout=delay)
            return not self.stop_event.is_set()

        stop_waiter = asyncio.create_task(
            self.stop_event.wait(), name='monitor_stopper')
        while True:
            if not await pause(0.2):
                break
            if self.mtime > self.load_time:
                self.load_time = self.mtime
                on_change_callback()
                if not await pause(2.0):
                    break

    def store(self):
        """Store the current element if not empty."""
        # pylint: disable=assignment-from-no-return
        el = self.el
        preserved_text = el.clean()
        if not el.is_empty():
            self.cur_group.add(el)
        if preserved_text:
            self.cur_group.add(preserved_text)
        self.el = PreservedText(parent=self.cur_group)

    def handle_comment(self, line):
        """Handle a comment line."""
        if line.startswith('#'):
            if not isinstance(self.el, PreservedText):
                self.store()
                self.el = PreservedText(parent=self.cur_group)
            self.el.add(line)
            return True
        else:
            return False

    def handle_title(self, line):
        """Handle a title line."""
        if line.startswith('@title:'):
            self.store()
            _, _, title = line.partition(':')
            self.root.title = title.strip()
            self.el = PreservedText(parent=self.cur_group)
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
            self.el = PreservedText(parent=self.cur_group)
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
        exc = None
        try:
            f = self.path.open(mode='rt', encoding='utf8')
        except OSError as exc:
            msg = f'Could not open {self.path}: {exc.strerror}'
            return None, None, msg
        else:
            return self._do_load(f)

    def _do_load(self, f):
        self.load_time = self.mtime
        reset_for_reload()
        self.root.reset()
        self.cur_group = self.root
        with f:
            self.el = PreservedText(parent=self.cur_group)
            for rawline in f:
                line = rawline.rstrip()
                if not (self.handle_comment(line)
                        or self.handle_title(line)
                        or self.handle_group(line)
                        or self.handle_marker(line)):
                    self.el.add(line)

        self.store()
        self.root.clean()
        self.root.update_keywords()
        if not self.root.groups:
            sys.exit(f'File {self.path} contains no groups')

        for el in self.root.walk(predicate=is_snippet):
            el.reset()
        return self.root, self.root.title, ''

    def save(self, root):
        """Save a snippet tree to the file."""
        with self.path.open('wt', encoding='utf8') as f:
            if root.title:
                f.write(f'@title: {root.title}\n')
            for el in root.walk():
                f.write(el.file_text())
                if isinstance(el, Group):
                    kws = el.keyword_set()
                    if not kws.is_empty():
                        f.write(kws.file_text())
        self.load_time = self.mtime

    @property
    def mtime(self) -> float | int:
        """The modification time of the loaded file."""
        try:
            st = self.path.stat()
        except OSError:
            return -1.0
        else:
            return st.st_mtime


class DefaultLoader(Loader):
    """A loader that reads from a text string."""

    def __init__(self, content: str, path: str):
        super().__init__(path)
        self.f = StringIO(content)
        self.on_change_callback: Callable[[], None] | None = None

    def load(self):
        """Load a tree of snippets from a file."""
        return self._do_load(self.f)

    async def become_manifest(self):
        """Create a Loader from a default loader."""
        loader = Loader(str(self.path), root=self.root)
        loader.save(self.root)
        loader.load()
        if self.on_change_callback:
            loader.start_monitoring(self.on_change_callback)
        return loader

    def start_monitoring(self, on_change_callback: Callable):
        """Just store the callback.."""
        self.on_change_callback = on_change_callback

    async def stop_monitoring(self):
        """Do nothing for the default loader."""


def save(path, root):
    """Save a snippet tree to a file."""
    with Path(path).open('wt', encoding='utf8') as f:
        if root.title:
            f.write(f'@title: {root.title}\n')
        for el in root.walk():
            f.write(el.file_text())
            if isinstance(el, Group):
                kws = el.keyword_set()
                if not kws.is_empty():
                    f.write(kws.file_text())


def backup_file(path):
    """Create a new backup of path.

    Up to 10 numbered backups are maintained.
    """
    path = Path(path)
    dirpath = path.parent
    name = path.name
    names = [f'{name}.bak{n}' for n in range(1, 11)]
    old_names = reversed(names[:-1])
    new_names = reversed(names[1:])
    for old_name, new_name in zip(old_names, new_names):
        src_path = dirpath / old_name
        if src_path.exists():
            with suppress(OSError):
                shutil.move(src_path, dirpath / new_name)
    with suppress(OSError):
        shutil.copy(path, dirpath / names[0])


def reset_for_reload():
    """Perform a 'system' reset.

    This is used when the entire snippet tree is be being reloaded.
    """
    Element.id_source = itertools.count()
    PlaceHolder.id_source = itertools.count()
    TextualElement.id_source = itertools.count()
    PreservedText.id_source = itertools.count()
    Snippet.id_source = itertools.count()
    KeywordSet.id_source = itertools.count()
    Group.id_source = itertools.count(1)


def reset_for_tests():
    """Perform a 'system' reset for test purposes.

    This is not intended for non-testing use.
    """
    reset_for_reload()


def is_type(obj, *, classinfo) -> bool:
    """Test if an object is an instance of the given types.

    This simply wraps the built-in ``isinstance``, but plays nicely with
    functools.partial.
    """
    return isinstance(obj, classinfo)


# Useful predicate functions for tree walking.
is_snippet = partial(is_type, classinfo=Snippet)
is_snippet_like = partial(is_type, classinfo=(Snippet, PlaceHolder))
is_group = partial(is_type, classinfo=Group)
