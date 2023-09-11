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
from io import StringIO
from pathlib import Path
from typing import (
    Callable, ClassVar, Iterable, Iterator, Literal, Sequence, TYPE_CHECKING,
    TypeAlias, TypeVar, cast)

from markdown_strings import esc_format

from . import colors
from .text import render_text

if TYPE_CHECKING:
    from rich.text import Text

class Sentinel:                        # pylint: disable=too-few-public-methods
    """A class to define sentinel values."""


ELT = TypeVar('ELT')
SENTINAL = Sentinel()


class CannotMove(Exception):
    """Inidication that a snippet of gruop cannot be moved."""


class FixedPointer:
    """A 'pointer' of where to insert a child within a group tree.

    An insertion point can be before or after a child. Within a group, an
    insertion point below one child is equal to an insertion point above the
    following child.

    Instances of this are considered immutable but subclasses may be mutable.
    """

    def __init__(self, child: GroupChild, *, after: bool):
        self.child: GroupChild = child
        self.after = after

    @property
    def next_in_group(self) -> GroupChild | None:
        """The next child within this child's group."""
        return self.child.next_in_group

    @property
    def addr(self) -> tuple[str, bool]:
        """The insertaion point in the form (uid, insert_after)."""
        return self.child.uid(), self.after

    def __eq__(self, other: object):
        """Test for equality wwith another pointer."""
        if not isinstance(other, FixedPointer):
            return False                                     # pragma: no cover

        is_equal = False
        if self.child is other.child:
            is_equal = (
                isinstance(self.child, PlaceHolder)
                or self.after == other.after)
        elif self.after and not other.after:
            is_equal = self.next_in_group is other.child
        elif not self.after and other.after:
            is_equal = other.next_in_group is self.child

        return is_equal

    def __repr__(self):
        return f'{self.__class__.__name__}({self.child.uid()}, {self.after})'


class Pointer(FixedPointer):
    """Base for the SnippetInsertionPointer and GroupInsertionPointer.

    This always points to a position that is different to the one occupied by
    the supplied ``child``, raising CannotMove during construction if this
    condition cannot be met.

    :child:
        The child that is planned to be moved.
    :pointers:
        All the possible pointer positions.
    """

    def __init__(self, child: GroupChild, pointers: list[FixedPointer]):
        super().__init__(child, after=False)
        self.pointers = pointers
        self.source: GroupChild = child
        invalid_pointers = (
            FixedPointer(child, after=False), FixedPointer(child, after=True))

        # Try to choose a starting point just above the source.
        self.idx = 0
        for i, p in enumerate(self.pointers):
            if p in invalid_pointers:
                self.idx = max(0, i -1)
                break

        # Now remove the invliad pointers, after which we may find that moving
        # is not possible.
        self.pointers = [
            p for p in self.pointers if p not in invalid_pointers]
        if not self.pointers:
            raise CannotMove

        p = self.pointers[self.idx]
        self.child = p.child
        self.after = p.after

    def move(self, *, backwards: bool = False) -> bool:
        """Move to the next insertion point.

        This performs the smallest possible move, which may results in an
        equivalent position.

        :backwards:
            If set then move the insertion point backwards.
        :return:
            True if an apparent movement occurred.
        """
        delta = -1 if backwards else 1
        if 0 <= self.idx + delta <= len(self.pointers) - 1:
            self.idx += delta
            p = self.pointers[self.idx]
            self.child = p.child
            self.after = p.after
            return True
        else:
            return False


class SnippetInsertionPointer(Pointer):
    """A 'pointer' of where to insert a snippet within the tree."""

    def __init__(self, snippet: Snippet):
        pointers: list[FixedPointer] = []
        s: SnippetLike
        for s in snippet.root.walk(
                predicate=is_snippet_like, group_depth_first=True):
            if s.is_first_in_group:
                pointers.append(FixedPointer(s, after=False))
            pointers.append(FixedPointer(s, after=True))

        super().__init__(snippet, pointers)

    def move_source(self) -> bool:
        """Move the source child to this insertion point."""
        child = self.source
        child.parent.remove(child)
        child.parent.clean()
        if self.after:
            self.child.parent.add(child, after=self.child)
        else:
            self.child.parent.add(child, before=self.child)
        self.child.parent.clean()
        return True


class GroupInsertionPointer(Pointer):
    """A 'pointer' of where to insert a group within the tree."""

    def __init__(self, group: Group):
        super().__init__(group, group.root.insertion_points())

    def move_source(self) -> bool:
        """Move the source child to this insertion point."""
        group = cast(Group, self.source)
        dest_group = cast(Group, self.child)
        group.parent.remove_group(group)
        group.parent.clean()
        if self.after:
            self.child.parent.add_group_as_group(group, after=dest_group)
        else:
            self.child.parent.add_group_as_group(group, before=dest_group)
        self.child.parent.clean()
        return True


class GroupChild:
    """Base for any class that mey be contained within a group tree.

    GroupChild instances provide a unique ID, available using a ``uid`` method.
    Such UIDs follow a simple naming convention, which other parts of the
    Clippet's code relies on. Snippets instances, for example, have UIDs of the
    form <snippet>-<n> (*e.g.* 'snippet-6'). The important ID forms are:

    snippet-<n>
        A simple (text) `Snippet` or a `MarkdownSnippet`.
    group-<n>
        A snippet `Group`.
    """

    id_source: Iterator[int] | None = None

    def __init__(self, parent: Group):
        self.parent: Group = parent
        self.dirty = True
        if self.id_source:
            self._uid = f'{self._uid_base_name()}-{next(self.id_source)}'
        else:
            self._uid = ''

    @property
    def root(self) -> Root:
        """The root of the containing tree."""
        return self.parent.root

    def depth(self) -> int:
        """Calculete the depth of this element within the snippet tree."""
        return self.parent.depth() + 1

    def uid(self) -> str:
        """Provide a unique ID for this element."""
        return self._uid

    @property
    def is_first_in_group(self) -> bool:
        """True if this child is the first in its group."""
        return self.parent.index_of(self) == 0

    def is_empty(self) -> bool:                   # pylint: disable=no-self-use
        """Determine if this element is empty.

        Subclasses must over-ride.
        """
        return True                                          # pragma: no cover

    def full_repr(self, *, end='\n', debug: bool = False):
        """Format a simple representation of this element.

        This is intended for test support. The exact format may change between
        releases.
        """
        body = self.body_repr()
        spc = ' ' if body else ''
        id_part = f' {self.uid()}' if debug else ''
        return f'{self.__class__.__name__}{id_part}:{spc}{body}'

    def body_repr(self) -> str:                   # pylint: disable=no-self-use
        """Format a simple representation of this element's body.

        This is intended for test support. The exact format may change between
        releases.
        """
        return ''                                            # pragma: no cover

    def clean(self) -> None:
        """Put this in the right place."""

    @property
    def next_in_group(self) -> GroupChild | None:
        """The child after this one."""
        return self.parent.next_child(self)

    @classmethod
    def _uid_base_name(cls) -> str:
        """Provide a base name for UID strings."""
        return cls.__name__.lower()


class Element:
    """An element in a tree of groups and snippets.

    This holds information relating to the input file's contents.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._source_lines: list[str] = []
        self.leading_text: list[str] = []
        self.trailing_text: list[str] = []

    @property
    def source_lines(self) -> Sequence[str]:
        """The source lines for this element."""
        return tuple(self._source_lines)

    @source_lines.setter
    def source_lines(self, value: Iterable[str]):
        self._source_lines = list(value)
        self.dirty = True

    def add_leading_text(self, lines: Sequence[str]):
        """Extend the leading text for this element."""
        self.leading_text.extend(lines)

    def add_trailing_text(self, lines: Sequence[str]):
        """Extend the trailing text for this element."""
        self.trailing_text.extend(lines)

    def is_empty(self) -> bool:
        """Determine if this element is empty."""
        return len(self.source_lines) == 0

    def file_text(self) -> str:                   # pylint: disable=no-self-use
        """Generate the text that should be written to a file."""
        return ''

    def clean(self) -> None:
        """Clean the source lines.

        Tabs are expanded and whitespace is trimmed from the end of each line.
        """
        self.source_lines = [
            line.expandtabs().rstrip() for line in self.source_lines]


class SnippetLike(GroupChild):
    """A base for all the Snippet and PlaceHolder classes."""


class PlaceHolder(Element, SnippetLike):
    """A place holder used in empty groups."""

    id_source: Iterator[int] | None = itertools.count()

    @property
    def is_first_in_group(self) -> bool:
        """Always false.

        A PlaceHolder is never considered to be first or last within a group.
        """
        return False                                         # pragma: no cover


class TextualElement(Element):
    """An `Element` that holds text."""

    marker:str = ''

    def add(self, line) -> None:
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

    def file_text(self) -> str:
        """Generate the text that should be written to a file."""
        s = [f'{line}\n' for line in self.leading_text]
        s.append(f'  {self.marker}\n')
        s.extend(f'    {line}\n' for line in self.source_lines)
        s.extend(f'{line}\n' for line in self.trailing_text)
        return ''.join(s)


class PreservedText(TextualElement, GroupChild):
    """Input file text that is preserved, but non-functional.

    This includes:

    - Additional vertical space.
    - Comment blocks.
    """

    id_source: Iterator[int] | None = None

    def file_text(self) -> str:
        """Generate the text that should be written to a file."""
        return ''                                            # pragma: no cover


class Snippet(TextualElement, SnippetLike):
    """A single, multiline snippet of text.

    This is used fro plain-text snippets and is also the base class for the
    `MarkdownSnippet`.
    """

    id_source: Iterator[int] | None = itertools.count()
    marker = '@text@'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._marked_lines = []

    @property
    def marked_lines(self) -> list[str]:
        """The snippet's lines, with keywords marked up.

        Keywords are surrounded by the Unicode characters u2e24 and 2e25. These
        look very similar to comma, so they are extremely unlikely to appear in
        non-marked up text. Immediately following the u2e24 characte is a
        single letter that is a key indicating the colour that will be used to
        highligh the keyword.
        """
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
    def marked_text(self) -> Text | str:
        """The snippet's text, with keywords marked up, rendered as Text.

        :return:
            The method returns a Text instamce, but subclasses may simply
            return a string.
        """
        lines = textwrap.dedent('\n'.join(self.marked_lines)).splitlines()
        return render_text('\n'.join(lines))

    def reset(self) -> None:
        """Clear any cached state."""
        self._marked_lines = []
        self.dirty = True

    def md_lines(self) -> list[str]:
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

    def set_text(self, text) -> None:
        """Set the text for this snippet."""
        self._marked_lines = []
        self.source_lines = text.splitlines()

    def clean(self) -> None:
        """Clean the source lines.

        Tabs are expanded and whitespace is trimmed from the end of each line.
        Trailing blank lines are deleted and common leading white space
        removed.
        """
        super().clean()
        lines = self._source_lines
        while lines and not lines[-1].strip():
            self.add_trailing_text([lines.pop()])
        self._source_lines[:] = textwrap.dedent('\n'.join(lines)).splitlines()

    @classmethod
    def _uid_base_name(cls) -> Literal['snippet']:
        """Provide base name for all types of Snippet."""
        return 'snippet'


class MarkdownSnippet(Snippet):
    """A snippet that is interpreted as Markdown text."""

    marker = '@md@'

    def md_lines(self) -> list[str]:
        """Provide snippet lines in Markdown format.

        This simply provides unmodified lines.
        """
        return self.body.splitlines()

    @property
    def marked_text(self) -> str:
        """The snippet's text, with keywords marked up."""
        lines = textwrap.dedent('\n'.join(self.marked_lines)).splitlines()
        return '\n'.join(lines)


class KeywordSet(TextualElement, GroupChild):
    """An element holding a set of keywords."""

    id_source: Iterator[int] | None = itertools.count()
    marker = '@keywords@'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.words = set()

    def add(self, line) -> None:
        """Add a entry to this set of keywords.

        The line is split at spaces to obtain the set of keywords.
        """
        super().add(line)
        new_words = self.source_lines[-1].split()
        self.words.update(new_words)

    @property
    def text(self) -> str:
        """Build the plain text for this snippet."""
        return '\n'.join(sorted(self.words))

    def file_text(self) -> str:
        """Generate the text that should be written to a file."""
        s = [f'  {self.marker}']
        s.extend(f'    {line}' for line in self.text.splitlines())
        text = '\n'.join(s)
        return text.rstrip() + '\n'

    def body_repr(self) -> str:
        """Format a simple representation of this element's body.

        This is intended for test support. The exact format may change between
        releases.
        """
        return f'{" ".join(sorted(self.words))}'

    def is_empty(self) -> bool:
        """Detemine if this keyword set is empty."""
        return not self.words

    @classmethod
    def combine(cls, parent, *keyword_sets) -> KeywordSet:
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
    children: list[GroupChild]
    parent: Group
    keyword_set: KeywordSet

    @property
    def ordered_groups(self) -> list[Group]:
        """The groups in user-defined order."""
        return []                                            # pragma: no cover

    def outline_repr(self, end='\n') -> str:
        """Format a simple group-only outline representation of the tree.

        This is intended for test support. The exact format may change between
        releases.
        """
        s = [self.name]
        s.extend(g.outline_repr(end='') for g in self.ordered_groups)
        return '\n'.join(s) + end

    @property
    def repr_full_name(self) -> str:
        """The full repr name of this group."""
        if self.parent and self.parent.parent:
            pfull_name = self.parent.repr_full_name if self.parent else ''
        else:
            pfull_name = ''
        if pfull_name:
            return f'{pfull_name}:{self.name}'
        else:
            return self.name

    def full_repr(self, end='\n', *, debug: bool = False) -> str:
        """Format a simple outline representation of the tree.

        This is intended for test support. The exact format may change between
        releases.
        """
        if debug:                                            # pragma: no cover
            s = [f'Group: {self.repr_full_name} {self.uid()}']
        else:
            s = [f'Group: {self.repr_full_name}']
        s.append(self.keyword_set.full_repr(end='', debug=debug))
        s.extend(
            c.full_repr(end='', debug=debug) for c in self.children
            if not isinstance(c, PlaceHolder))
        s.extend(g.full_repr(end='', debug=debug) for g in self.ordered_groups)
        return '\n'.join(s) + end


class Group(GroupDebugMixin, Element, GroupChild):
    """A group of snippets and/or sub groups."""

    id_source: Iterator[int] | None = itertools.count()
    all_tags: ClassVar[set[str]] = set()

    def __init__(self, name, parent=None, tag_text=''):
        super().__init__(parent)
        self.name = name
        self.title = ''   # TODO: What is this?
        self.groups: dict[str, Group] = {}
        self._ordered_groups: list[str] = []
        tags = {t.strip() for t in tag_text.split()}
        self.tags = sorted(tags)
        for t in self.tags:
            self.all_tags.add(t)
        self.children: list[GroupChild] = [KeywordSet(parent=self)]
        self.keyword_set: KeywordSet

    @property
    def ordered_groups(self) -> list[Group]:
        """The groups in user-defined order."""
        return [self.groups[name] for name in self._ordered_groups]

    def rename(self, name) -> None:
        """Change the name of this group."""
        self.parent.rename_child_group(self.name, name)
        self.name = name

    def rename_child_group(self, old_name: str, new_name: str) -> None:
        """Update to reflect a name change for a child group."""
        idx = self._ordered_groups.index(old_name)
        self._ordered_groups[idx] = new_name
        self.groups[new_name] = self.groups.pop(old_name)

    def add_group(self, name, after: str = '') -> Group:
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
            self, child: GroupChild,
            after: GroupChild | Literal[0] | None = None,
            before: GroupChild | None = None,
        ) -> None:
        """Add a new snippet as a child of this group."""
        # TODO: Consider making this handle groups as well.
        children = self.children
        if after == 0:
            p = 0
        elif after:
            p = children.index(after) + 1
        elif before:
            p = children.index(before)
        else:
            p = len(children)
        self.children[p:p] = [child]
        child.parent = self

    # TODO: Name is wrong!
    def add_group_as_group(
            self, child: Group,
            after: Group | None = None,
            before: Group | None = None,
        ) -> None:
        """Add a existing group as a child of this group.

        This is used when reorgnising the group hierarchy.
        """
        ordered_groups = self._ordered_groups
        if after:
            p = ordered_groups.index(after.name) + 1
        elif before:
            p = ordered_groups.index(before.name)
        ordered_groups[p:p] = [child.name]
        child.parent = self
        self.groups[child.name] = child

    def add_new(self) -> Snippet:
        """Add a new snippet at the start of this group."""
        snippet = MarkdownSnippet(parent=self)
        self.add(snippet, after=0)
        return snippet

    def remove(self, child) -> None:
        """Remove a child element from this group."""
        with suppress(ValueError):
            self.children.remove(child)
        snippets = [el for el in self.children if isinstance(el, Snippet)]
        if not snippets:
            self.children.append(PlaceHolder(parent=self))

    def remove_group(self, child) -> None:
        """Remove a child element from this group."""
        self.groups.pop(child.name)
        self._ordered_groups.remove(child.name)

    def clean(self) -> None:
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
        self.keyword_set = KeywordSet.combine(self, *keyword_sets)

        if self.parent:
            snippets = [el for el in self.children if isinstance(el, Snippet)]
            if not snippets:
                self.children.append(PlaceHolder(parent=self))

    def next_child(self, child: GroupChild) -> GroupChild | None:
        """Get the next child, of the same basic type, after this one."""
        children: Sequence[GroupChild]
        if isinstance(child, Group):
            children = self.ordered_groups
        else:
            children = self.children
        idx = children.index(child) + 1
        return children[idx] if idx < len(children) else None

    def insertion_points(self) -> list[FixedPointer]:
        """Determine all insertion poins."""
        groups = self.ordered_groups
        pointers: list[FixedPointer] = []
        for i, g in enumerate(groups):
            pointers.append(FixedPointer(g, after=False))
            if i == len(groups) - 1:
                pointers.append(FixedPointer(g, after=True))
            pointers.extend(g.insertion_points())
        return pointers

    def basic_walk(
            self, *,
            backwards: bool = False,
            group_depth_first: bool = False,
        ) -> Iterator[GroupChild]:
        """Iterate over the entire tree of groups and snippets.

        :backwards:
            If set the walk in reverse order; i.e. the very last snippet is
            visited first.
        :group_depth_first:
            If set then (for a forwards walk) child groups are yielded before
            the group itself.
        """
        if backwards:
            for group in reversed(self.ordered_groups):
                if not group_depth_first:
                    yield group
                yield from group.basic_walk(backwards=backwards)
                if group_depth_first:
                    yield group
            yield from reversed(self.children)
        else:
            yield from self.children
            for group in self.ordered_groups:
                if not group_depth_first:
                    yield group
                yield from group.basic_walk(backwards=backwards)
                if group_depth_first:
                    yield group

    def snippets(self) -> Iterator[Snippet]:
        """Iterate over all child snippets."""
        yield from (el for el in self.children if isinstance(el, Snippet))

    def step_group(self, *, backwards: bool = False) -> Group | None:
        """Get the group before or after this onw."""
        for el in self.root.walk(
                predicate=is_group, after=self, backwards=backwards,
                group_depth_first=backwards):
            return el
        return None

    def index_of(self, el: GroupChild) -> int:
        """Calculate the index of an element within its contaning group.

        :return:
            A value between 0 and len(<container>) - 1.
        """
        seq: Sequence[GroupChild]
        if isinstance(el, Snippet):                              # noqa: SIM108
            seq = self.children
        else:
            seq = self.ordered_groups                        # pragma: no cover
        return seq.index(el)

    def keywords(self) -> set[str]:
        """Provide all the keywords applicable to this group's snippets."""
        return self.keyword_set.words

    @property
    def full_name(self) -> str:
        """The full name of this group."""
        pfull_name = self.parent.full_name if self.parent else ''
        if pfull_name:
            return f'{pfull_name} : {self.name}'
        elif self.name != '<ROOT>':
            return self.name
        else:
            return ''

    def file_text(self) -> str:
        """Generate the text that should be written to a file."""
        s = [f'{line}\n' for line in self.leading_text]
        if self.tags:
            s.append(f'{self.full_name} [{" ".join(self.tags)}]\n')
        else:
            s.append(f'{self.full_name}\n')
        s.extend(f'    {line}\n' for line in self.source_lines)
        s.extend(f'{line}\n' for line in self.trailing_text)
        return ''.join(s)


class Root(Group):
    """A group that acts as the root of the snippet tree."""

    @property
    def root(self) -> Root:
        """This instance; *i.e.* the root of this tree."""
        return self

    def depth(self) -> Literal[0]:
        """Return 0, the depth tree root."""
        return 0

    def reset(self) -> None:
        """Reset to initialised state.

        This is used prior to a complete relead.
        """
        self.groups: dict[str, Group] = {}
        self._ordered_groups = []

    def walk(
            self,
            predicate: Callable[[GroupChild], type[ELT] | None],
            *,
            after: GroupChild | None = None,
            backwards: bool = False,
            group_depth_first: bool = False,
        ) -> Iterator[ELT]:
        """Iterate over the entire tree of groups and snippets.

        :predicate:
            A function  taking an 'Element' as it only argument. Only elements
            for which this returns a true value are visited.
        :after:
            If provided,skip all elements upto and including this one.
        :backwards:
            If set the walk in reverse order; i.e. last snippt is visited
            first.
        :group_depth_first:
            If set then (for a forwards walk) child groups are yielded before
            the group itself.
        """
        basic_walk = self.basic_walk(
            backwards=backwards, group_depth_first=group_depth_first)
        if after:
            for el in basic_walk:
                if el is after:
                    break
        for el in basic_walk:
            if predicate(el):
                yield cast(ELT, el)

    def find_group_child(self, uid) -> GroupChild | None:
        """Find an group child element with the given UID."""
        for el in self.walk(predicate=is_group_child):
            if el.uid() == uid:
                return el
        return None

    def first_snippet(self) -> Snippet | None:
        """Get the first snippet, if any."""
        for el in self.walk(predicate=is_snippet):
            return cast(Snippet, el)
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

    def update_keywords(self) -> None:
        """Update the keyword tracker with any changes."""
        all_keywords: set[str] = set()
        for group in self.walk(is_group):
            all_keywords |= group.keywords()
        colors.keywords.apply_changes(all_keywords)


# TODO: Not Python 3.8 compatible.
ParsedElement: TypeAlias = PreservedText | Snippet | KeywordSet | Group


class Loader:
    """Encapsulation of snippet loading machinery."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, path: str, *, root: Root | None = None):
        self.path = Path(path)
        self.root = root or Root('<ROOT>')
        self.el: ParsedElement = Snippet(parent=self.root)
        self.last_added: ParsedElement | None = None
        self.cur_group: Group = Group('')
        self.monitor_task: asyncio.Task | None = None
        self.load_time: float = 0.0
        self.stop_event = asyncio.Event()
        self.leading_text: list[str] = []

    def start_monitoring(self, on_change_callback: Callable) -> None:
        """Start a task that monitors for change to the loaded file."""
        self.monitor_task = asyncio.create_task(
            self.monitor(on_change_callback), name='monitor_file')

    async def stop_monitoring(self) -> None:
        """Stop monitoring for changes to the loaded file."""
        if self.monitor_task:
            self.stop_event.set()
            await self.monitor_task

    async def monitor(self, on_change_callback: Callable) -> None:
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

    def store(self) -> None:
        """Store the current element if not empty."""
        el = self.el
        el.clean()
        if not el.is_empty():
            if isinstance(el, PreservedText):
                self.leading_text.extend(el.source_lines)
            else:
                el.add_leading_text(self.leading_text)
                self.leading_text = []
                self.cur_group.add(el)
                self.last_added = el
        self.el = PreservedText(parent=self.cur_group)

    def handle_comment(self, line) -> bool:
        """Handle a comment line."""
        if line.startswith('#'):
            if not isinstance(self.el, PreservedText):
                self.store()
                self.el = PreservedText(parent=self.cur_group)
            self.el.add(line)
            return True
        else:
            return False

    def handle_title(self, line) -> bool:
        """Handle a title line."""
        if line.startswith('@title:'):
            self.store()
            _, _, title = line.partition(':')
            self.root.title = title.strip()
            self.el = PreservedText(parent=self.cur_group)
            return True
        else:
            return False

    def handle_group(self, line) -> bool:
        """Handle a group start line."""
        r_group = re.compile(r'([^ ].*)')
        m = r_group.match(line)
        if m:
            self.store()
            text = m.group()
            sub_groups = [g.strip() for g in text.split(':')]
            self.cur_group = self.root.add_group(sub_groups.pop(0))
            self.cur_group.add_leading_text(self.leading_text)
            self.leading_text = []
            while sub_groups:
                self.cur_group = self.cur_group.add_group(sub_groups.pop(0))
            self.last_added = self.cur_group
            self.el = PreservedText(parent=self.cur_group)
            return True
        else:
            return False

    def handle_marker(self, line) -> bool:
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

    def load(self) -> tuple[Root | None, str, str]:
        """Load a tree of snippets from a file."""
        exc: OSError | None = None
        try:
            f = self.path.open(mode='rt', encoding='utf8')
        except OSError as exc:
            msg = f'Could not open {self.path}: {exc.strerror}'
            return None, '', msg
        else:
            return self._do_load(f)

    def _do_load(self, f) -> tuple[Root, str, str]:
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
        if self.last_added:
            self.last_added.add_trailing_text(self.leading_text)
        else:
            self.root.add_trailing_text(self.leading_text)
        return self.root, self.root.title, ''

    def save(self, root) -> None:
        """Save a snippet tree to the file."""
        with self.path.open('wt', encoding='utf8') as f:
            if root.title:
                f.write(f'@title: {root.title}\n')
            for el in root.walk(predicate=is_group_child):
                f.write(el.file_text())
                if isinstance(el, Group):
                    kws = el.keyword_set
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

    def load(self) -> tuple[Root, str, str]:
        """Load a tree of snippets from a file."""
        return self._do_load(self.f)

    async def become_manifest(self) -> Loader:
        """Create a Loader from a default loader."""
        loader = Loader(str(self.path), root=self.root)
        loader.save(self.root)
        loader.load()
        if self.on_change_callback:
            loader.start_monitoring(self.on_change_callback)
        return loader

    def start_monitoring(self, on_change_callback: Callable) -> None:
        """Just store the callback.."""
        self.on_change_callback = on_change_callback

    async def stop_monitoring(self) -> None:
        """Do nothing for the default loader."""


def backup_file(path) -> None:
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


def reset_for_reload() -> None:
    """Perform a 'system' reset.

    This is used when the entire snippet tree is be being reloaded.
    """
    Group.id_source = itertools.count(1)
    KeywordSet.id_source = itertools.count()
    PlaceHolder.id_source = itertools.count()
    Snippet.id_source = itertools.count()


def reset_for_tests() -> None:
    """Perform a 'system' reset for test purposes.

    This is not intended for non-testing use.
    """
    reset_for_reload()


def is_group_child(obj: GroupChild) -> type[GroupChild] | None:
    """Test if object is a Element."""
    return GroupChild if isinstance(obj, GroupChild) else None


def is_snippet(obj: GroupChild) -> type[Snippet] | None:
    """Test if object is a Snippet."""
    return Snippet if isinstance(obj, Snippet) else None


def is_group(obj: GroupChild) -> type[Group] | None:
    """Test if object is a Group."""
    return Group if isinstance(obj, Group) else None


def is_snippet_like(obj: GroupChild) -> type[SnippetLike] | None:
    """Test if object is a Group."""
    return SnippetLike if isinstance(obj, SnippetLike) else None
