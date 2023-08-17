"""Text specific support."""
from __future__ import annotations

import re

from rich.errors import StyleSyntaxError
from rich.style import Style
from rich.text import Span, Text

from .colors import keyword_colors

# We 'smuggle' keyword information by surrounding them with specific Unicode
# low quotes. These look quite like commas, making it extremely unlikely that
# anyone would would use them a snippet text.
re_keyword = re.compile('\u2e24([^\u2e25]*)\u2e25')
re_keyword_start = re.compile('\u2e24[^\u2e25]*')


def gen_highlight_spans(
        text: str, base_style: Style, off: int) -> tuple[list[Span], str]:
    """Split text into spans based on highlighting."""
    parts = re_keyword.split(text)
    spans = []
    new_parts = []
    for i, p in enumerate(parts):
        if i & 1:
            substr = p[1:]
            cc = p[0]
            color = keyword_colors.get(cc, 'green')
            style = base_style + Style(color=color)
        else:
            substr = re_keyword_start.sub('', p)
            substr = substr.replace('\u2e25(', '')
            style = base_style
        if substr:
            new_parts.append(substr)
            spans.append(Span(off, off + len(substr), style))
            off += len(substr)

    return spans, ''.join(new_parts)


def force_style(st: str | Style) -> Style:
    """Convert any string to a Style instance."""
    if isinstance(st, str):                                  # pragma: no cover
        try:
            return Style.parse(st)
        except StyleSyntaxError:
            return Style()
    else:
        return st


def render_text(text: Text | str) -> Text:
    """Render specially marked up text."""
    if isinstance(text, str):
        text = Text(text, spans=[Span(0, len(text), Style())])
    raw_text = text.plain
    if '\u2e24' in raw_text:
        new_spans = []
        new_parts = []
        off = 0
        for span in text.spans:
            substr = raw_text[span.start:span.end]
            new_subspans, new_substr = gen_highlight_spans(
                substr, force_style(span.style), off)
            new_spans.extend(new_subspans)
            new_parts.append(new_substr)
            off += len(new_parts[-1])
        return Text(''.join(new_parts), spans=new_spans)
    else:
        return text
