"""Richish markup support for Textual display.

This uses some simple markup that borrows from both Markdown and
reStructureText.

It was developed an way of generating the Snippets help page. I tried using
Markdown, but at time of writing Textual and Markdown combined do not provide
the rich level of formatting I want.

In brief, the markup rules are:

- Indentation **must** be in multiple of 4 spaces. Each additional 4 space
  indent increases the logical element level by 1.

- The input is a block of lines, separated by one or more blank lines.
  Each block can be a heading, paragraph, definition, *etc*.

- Headings are like Markdown, one or more leading hash characterss.

- Defnitions look like this::

      word or phrase
          The description; indented by 4 spaces, may be multiple lines and
          multiple blocks.

- Literal text blocks (code blocks) look like::

      some example Python:<python>:

          def myfunc():
              ...

      some uninterpreted text::

         line 1
         line 2

- Within most blocks, inline emphasis is generically supported using the
  construct::

      :style-name:`some-text`

    For example::

      :italic:`italic text`

  The delimiters are backticks, *not* single quotation marks.  There is a set
  of standard names; which also have more compact alternatives::

      :italic:`italic`              or     *italic*
      :bold:`bold`*                 or     **bold**
      :bold italic:`bold italic`    or     ***bold italic***
      :underline:`underlined`       or     _underlined_
      :strike:`strike out text`     or     ~strike out text~
      :emph:`emphasis`              or     `emphasis`
      :code:`literal`               or     ``literal``

  Other style-names are, currently, simply used as Rich style names. allowing
  fairly arbitrary styling. For example::

      :red bold italic underline:`This is really serious!`

Note that the parser code is quite simple and the result of incorrectly
formatted input text is likely to result in a run-time error or garbage out.
"""
from __future__ import annotations

# TODO:                                                             noqa: TD005
#     There should be some way to define class names so that instead of::
#
#          :red bold italic underline:`This is really serious!`
#
#     we could do::
#
#          :urgent:`This is really serious!`

import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Generic, Iterator, TypeVar

from rich.style import Style
from rich.text import Text
from textual.widgets import Markdown, Static

T = TypeVar('T')

STD_IND = 4

rc_heading = re.compile(r'''(?x)
    \s *                # Optional spaces
    (?P<hashes>[#] +)   # Initial hashes
    \s *                # Optional spaces
    (?P<heading>.*)     # The heading text.
''')
rc_code_block_start = re.compile(r'''(?x)
    : (?:                   # A colon
        <                   # Optionallly <lang>
        (?P<lang> [^:] + )
        >
    ) ?
    :                       # Second colon
    $                       # Must be ad end of line
''')
rc_inline_markup = re.compile(r'''(?x)
    ( . *? )                    # Leading text.
    (?:
        (?:
            ( \*\* )
            ( [^*] +? )         # Emphasised text
            ( \*\* )
        )
        | (?:
            (?P<italic> \* )
            ( [^*] +? )         # Emphasised text
            ( \* )
        )
    )
''')
rc_inline_markup = re.compile(r'''(?x)
    ( . *? )                    # Leading text.
    (?P<emph>                   # Opening emphasis chars
           (?:                  #     *, ** or ***
               [*] {1,3}
           )
        |  (?:                  #     _ (imderscore) or ~ (tilde)
            [~_] {1}
           )
        |  (?:                  #     double `` (backticks)
            [``] {2}
           )
    )
    (?P<text> [^*] +? )         # Epmhasised text
    (?P=emph)
''')
rc_inline_class_markup = re.compile(r'''(?x)
    ( . *? )                # Leading text.
    (?:
      :
      (?P<class>              # Optional leading part
          [^:] +?
      )
      :
    ) ?
    (?P<emph>               # Opening backtick
       [`]
    )
    (?P<text> [^*] + )      # Epmhasised text
    (?P=emph)
''')

style_lookup: dict[str, str | Style] = {
    '*': 'italic',
    '**': 'bold',
    '***': 'bold italic',
    '_': 'underline',
    '~': 'strike',
    '``': Style(color='bright_blue', italic=True),
    'code': Style(color='bright_blue', italic=True),
}


def dedent_lines(lines: list[str]) -> tuple[int, list[str]]:
    """Remove common leading space from a block of lines.

    :return:
        A 2-tuple. The firs element is the logical level and the second is a
        list of the dedented lines.
    """
    newlines = textwrap.dedent('\n'.join(lines)).splitlines()
    return (len(lines[0]) - len(newlines[0])) // STD_IND, newlines


def ind(line):
    """Calculate physical indentation of an input text line."""
    return len(line) - len(line.lstrip())


def ind_level(line):
    """Calculate logical indentation level of an input text line."""
    return ind(line) // STD_IND


class PushbackIter(Generic[T]):
    """An iterator that support pushing back values."""

    def __init__(self, s: Iterator[T]):
        self.s = s
        self.stack: list[T] = []

    def push(self, value: T):
        """Push a value back input the input stream."""
        self.stack.append(value)

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        if self.stack:
            return self.stack.pop()
        else:
            return next(self.s)


class BlockTokeniser:                  # pylint: disable=too-few-public-methods
    """A simple parser for simple form of markup."""

    def __init__(self, text):
        lines = text.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)                                     # pragma: no cover
        while lines and not lines[-1].strip():
            lines.pop()                                      # pragma: no cover

        self.it = PushbackIter(iter(lines))
        self.state = 'idle'

    def blocks(self):
        """Yield basic blocks of text."""
        block = []
        for line in self.it:
            if line.strip():
                block.append(line)
            elif block:
                yield block
                block = []
        if block:
            yield block


def match_block(blocks, token_types):
    """Try to consume a block of lines, converting it to an Element."""
    for tok_type in token_types:
        m, lines = tok_type.consume_block(blocks)
        if lines is not None:
            return tok_type, m, lines

    return None, None, None


class Element:                         # pylint: disable=too-few-public-methods
    """Base for all markup text elements."""

    def __init__(self, parent, classes=()):
        self.parent = parent
        self.children = []
        self.classes = set(classes)

    def dump(self):                                          # pragma: no cover
        """Dump tree."""
        for el in self.children:
            print(el)
            el.dump()


@dataclass
class TextElement:
    """A text string with styling information."""

    text: str
    style: str | Style = ''


class BlockElement(Element):
    """Base for all markup block elements; heading, paragraph, *etc*."""

    widget_class: type = Static
    margin_adjust = 0

    def __init__(self, lines, parent, classes=(), _match=None):
        super().__init__(parent, classes)
        self.ind_level, self.lines = dedent_lines(lines)

    @property
    def level(self):                                         # pragma: no cover
        """The level of this element."""
        if self.parent:
            return self.parent.level + 1
        else:
            return 0

    @property
    def margin_level(self):
        """The margin level of this element."""
        if self.parent:
            return self.parent.margin_level + 1 + self.margin_adjust
        else:
            return 0                                         # pragma: no cover

    @classmethod
    def consume_block(cls, blocks):
        """Try to consume a block of lines, creating a suitable Element."""
        try:
            lines = next(blocks)
        except StopIteration:
            return None, None

        m = cls.match(lines)
        if m is not None:
            return m, lines
        else:
            blocks.push(lines)
            return None, None

    @classmethod
    def match(cls, _lines):
        """See if a block of lines is a match for this type of element."""
        return True                                          # pragma: no cover

    def gather_children(self, blocks):
        """Consume any child paragraphs."""

    def widget_text(self):
        """Form the text used to populate this element's widget."""
        return ' '.join(self.lines)

    def widget(self):
        """Create a widget for this elment."""
        w = self.widget_class(
            self.widget_text(), classes=' '.join(self.classes))
        top, right, bottom, left = w.styles.margin
        left = 2 * self.margin_level
        w.styles.margin = top, right, bottom, left
        return w

    def generate(self):
        """Generate Textual widgets for this document."""
        yield self.widget()
        for child in self.children:
            yield from child.generate()

    def _snippet(self) -> str:                    # pylint: disable=no-self-use
        """Format a snippet of text for use by __repr__."""
        return ''                                            # pragma: no cover

    def __repr__(self):
        ret = f'{self.__class__.__name__}({self.level}/{self.ind_level}'
        ret += f' {self._snippet()})'
        return ret


class Paragraph(BlockElement):         # pylint: disable=too-few-public-methods
    """A simple paragraph.

    A paragraph in stored as a sequence of TextElement instances.
    """

    def __init__(self, lines, parent, classes=(), _match=None):
        classes = [*classes, 'paragraph']
        super().__init__(lines, parent, classes)
        self.ind_level, self.lines = dedent_lines(lines)
        self._elements = None

    def _snippet(self) -> str:
        """Format a snippet of text for use by __repr__."""
        return self.lines[0]                                 # pragma: no cover

    @property
    def elements(self):
        """The paragraph content as a sequence of TextElement instances."""
        if self._elements is None:
            text = ' '.join(self.lines)
            self._elements = []
            while text:
                m: re.Match | None
                ma = rc_inline_markup.match(text)
                mb = rc_inline_class_markup.match(text)
                if ma and mb:
                    m = ma if ma.group(1) < mb.group(1) else mb
                else:
                    m = ma or mb
                if m:
                    if mb:
                        name = m.group('class')
                        style_name = style_lookup.get(name, name)
                    else:
                        style_name = style_lookup.get(m.group('emph'), '')
                    self._elements.append(TextElement(m.group(1)))
                    self._elements.append(
                        TextElement(m.group('text'), style_name))
                    text = text[len(m.group()):]
                else:
                    self._elements.append(TextElement(text))
                    text = ''
        return self._elements

    @classmethod
    def match(cls, lines):
        """Match a block of lines as a paragraph."""
        if len(lines) > 0:
            return ind_level(lines[0])
        return None                                          # pragma: no cover

    def widget_text(self):
        """Form the text used to populate this element's widget."""
        t = Text()
        for el in self.elements:
            t.append(el.text, style=el.style)
        return t

    def gather_children(self, blocks):
        """Consume any child paragraphs."""
        self.gather_code_block(blocks)

    def gather_code_block(self, blocks):
        """Consume any immediately following code block."""
        m = rc_code_block_start.search(self.lines[-1])
        if m:
            # Everything indented more than this paragraph is the literal text.
            lit_blocks = []
            for lines in blocks:
                if ind(lines[0]) <= self.ind_level * STD_IND:
                    blocks.push(lines)
                    break
                lit_blocks.append(lines)

            if lit_blocks:
                self.children.append(
                    CodeBlock(lit_blocks, self, m.group('lang')))
                self.lines[-1] = self.lines[-1][:-len(m.group()) + 1]


class CodeBlock(Paragraph):
    """A block of code or uninterpreted text."""

    widget_class: type = Markdown
    margin_adjust = -1

    def __init__(self, blocks, parent, lang):
        lines = list(blocks[0])
        for block in blocks[1:]:                             # pragma: no cover
            lines.append('')
            lines.extend(block)
        super().__init__(lines, parent, ['code'])
        self.lang = lang

    def widget_text(self):
        """Form the text used to populate this element's widget."""
        lang = self.lang or ''
        text = '\n'.join(self.lines)
        return f'~~~{lang}\n{text}\n~~~'

    def _snippet(self) -> str:
        """Format a snippet of text for use by __repr__."""
        return f'{self.lang}: {self.lines[0]}'               # pragma: no cover


class Definition(Paragraph):
    """A two part paragraph definining a term.

    A defintion is formatted as::

        Python
            A high level scripting language that is extremly popular throughout
            the entire World.
    """

    def __init__(self, lines, parent, classes=(), _match=None):
        classes = [*classes, 'term_name']
        super().__init__(lines, parent, classes)
        self.lines, description = self.lines[0:1], self.lines[1:]
        para = Paragraph(description, self, ['term_para', 'term_para_1'])
        para.ind_level += self.ind_level
        self.children = [para]

    @classmethod
    def match(cls, lines):
        """See if a block of lines is formatted as a definition."""
        if len(lines) > 1:
            a = ind_level(lines[0])
            b = ind_level(lines[1])
            if b == a  + 1:
                return a
        return None

    def gather_children(self, blocks):
        """Consume any child paragraphs."""
        self.children[0].gather_children(blocks)
        tok_types = [Section, Definition, Paragraph]
        while True:
            tok_type, m, lines = match_block(blocks, tok_types)
            if tok_type is Section:
                blocks.push(lines)
                break
            if tok_type:
                if m < self.children[0].ind_level:
                    blocks.push(lines)
                    break
                element = tok_type(lines, self, (), m)
                element.gather_children(blocks)
                self.children.append(element)
            else:
                break


class Section(BlockElement):           # pylint: disable=too-few-public-methods
    """A section.

    This consistes of a heading and one or more paragraphs
    """

    def __init__(self, lines, parent, classes=(), match=None):
        self.heading_level = len(match.group('hashes'))
        classes = [
            *classes, 'heading', f'heading_{self.heading_level}']
        super().__init__(lines, parent, classes)
        self.lines = [match.group('heading')]

    @classmethod
    def match(cls, lines):
        """See if a block of lines is a match for this type of element."""
        return rc_heading.match(lines[0])

    def gather_children(self, blocks):
        """Consume any child paragraphs."""
        tok_types = [Section, Definition, Paragraph]
        while True:
            tok_type, m, lines = match_block(blocks, tok_types)
            if tok_type is Section:
                n = len(m.group('hashes'))
                if n <= self.heading_level:
                    blocks.push(lines)
                    break
            if tok_type:
                element = tok_type(lines, self, (), m)
                element.gather_children(blocks)
                self.children.append(element)
            else:
                break


class Document(Element):
    """An entire document.

    This holds a sequence of Sections and paragraphs.
    """

    top_tokens: ClassVar[list[type[Element]]] = [
        Section,
        Definition,
        Paragraph,
    ]
    level = -1
    margin_level = -1

    def __init__(self, block_tokeniser):
        """Yield a sequence of markup elements."""
        super().__init__(None)
        blocks = PushbackIter(block_tokeniser.blocks())
        while True:
            tok_type, m, lines = match_block(blocks, self.top_tokens)
            if tok_type:
                element = tok_type(lines, self, (), m)
                element.gather_children(blocks)
                self.children.append(element)
            else:
                break

    def generate(self):
        """Generate Textual widgets for this document."""
        for child in self.children:
            yield from child.generate()


def generate():
    """Generate populated widgets for the help text."""
    help_path = Path(__file__).parent / 'help.txt'
    doc = Document(BlockTokeniser(help_path.read_text()))
    yield from doc.generate()


if __name__ == '__main__':
    test_help_path = Path(__file__).parent / 'help.txt'
    test_doc = Document(BlockTokeniser(test_help_path.read_text()))
    test_doc.dump()
    for widget in test_doc.generate():
        print(widget.classes)
