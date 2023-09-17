"""Loading and saving the clippets file.

The clippets file contains a mixture of the following:

Comments
    Any unindented line that starts with a hash ('#').

One-off directives.
    Any unindented line that starts with the 'at' ('@') symbol. The currently
    recognised directives are:

    @title: <text>

Group plus tag names
    Any non-indended line that is not a comment. Tag names appear after the
    group name and within brackts ('[' and ']'). Tags are separated by spaces.
    The file format is basically flat, but colons (':') may be used to indicate
    nested groups. For example 'Main:Sub' defines a group 'Sub' that is a child
    of the group 'Main'.

Element start markers
    An indented line starting and ending with 'at' ('@') symbols.
    The current valid markers are:

    @keywords@
        The content is split into a set of (white space separated) keywords.
    @md@
        The content is treated as Markdown text.
    @text@
        The content is treated as  plain text.

Content
    Indented or blank lines that follow a start marker.

Uninterpreted
    Any other lines.

All content, including comments and uninterpreted text is stored during
loading and stored as a nested tree of groups.

When a (possibly modified) tree is saved, the output should always be a close
analogue of the original input. There will be some notable differences.

- Indentation of markers and content will be 2 and 4 spaces respectively.
- All keywords within a group get written at the start of the group and they
  are sorted before writing.
"""

import pytest

from support import clean_text, populate

from clippets import snippets


def dump(*strings):                                          # pragma: no cover
    """Dump one ore mor blocks of text."""
    print('--------')
    for text in strings:
        for line in text.splitlines(True):
            print(f'  {line!r}')
        print('--------')


def load(path_name: str):
    """Load snippets from a file."""
    loader = snippets.Loader(path_name)
    *ret, _exc = loader.load()
    return ret


def save(path_name: str, root):
    """Load snippets from a file."""
    loader = snippets.Loader(path_name)
    return loader.save(root)


# TODO: Support empty or non-existant file.
def test_load_empty_file(snippet_infile):
    """An empty snippet file is considered an error."""
    with pytest.raises(SystemExit) as info:
        load(snippet_infile.name)
    expected = f'File {snippet_infile.name} contains no groups'
    assert str(info.value) == expected


def test_single_empty_group(snippet_infile):
    """A file with at least one group is valid, even without any snippets.

    The first element in the group will be an empty keywrod set.
    """
    populate(snippet_infile, '''
        Main
    ''')
    root, title = load(snippet_infile.name)
    assert title == ''
    expect = clean_text('''
        <ROOT>
        Main''')
    assert root.outline_repr() == expect
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:''')
    assert expect == root.full_repr()


def test_single_entry_group(snippet_infile):
    """A file with one snippet is valid."""
    populate(snippet_infile, '''
        Main
          @text@
            Snippet 1
    ''')
    root, title = load(snippet_infile.name)
    assert title == ''
    expect = clean_text('''
        <ROOT>
        Main''')
    assert root.outline_repr() == expect
    expect = clean_text(r'''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
    ''')
    assert expect == root.full_repr()


def test_single_markdown_snipper(snippet_infile):
    """A file with one snippet is valid."""
    populate(snippet_infile, '''
        Main
          @md@
            Snippet 1
    ''')
    root, title = load(snippet_infile.name)
    assert title == ''
    expect = clean_text('''
        <ROOT>
        Main''')
    assert root.outline_repr() == expect
    expect = clean_text(r'''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        MarkdownSnippet: 'Snippet 1'
    ''')
    assert expect == root.full_repr()


def test_leading_blank_line(snippet_infile):
    """A leading blank line is stored."""
    populate(snippet_infile, '''
        |
        Main
          @md@
            Snippet 1
    ''')
    root, title = load(snippet_infile.name)
    assert title == ''
    expect = clean_text('''
        <ROOT>
        Main''')
    assert root.outline_repr() == expect
    expect = clean_text(r'''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        MarkdownSnippet: 'Snippet 1'
    ''')
    assert expect == root.full_repr()


def test_keywords(snippet_infile):
    """Keywords are stored within a group.

    Multiple groups are combined and stored as the first child element of the
    group.
    """
    populate(snippet_infile, '''
        Main
          @keywords@
            one two
          @text@
            Snippet 1

        Second
          @md@
            Snippet 2
          @keywords@
            three four
          @keywords@
            five three
    ''')
    root, _ = load(snippet_infile.name)
    expect = clean_text('''
        <ROOT>
        Main
        Second
    ''')
    assert root.outline_repr() == expect
    expect = clean_text(r'''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet: one two
        Snippet: 'Snippet 1'
        Group: Second
        KeywordSet: five four three
        MarkdownSnippet: 'Snippet 2'
    ''')
    assert expect == root.full_repr()


def test_simple_single_snippet_is_preserved(snippet_infile, snippet_outfile):
    """Writing a file preserves a single snippit correctly."""
    expected = clean_text('''
        Main
          @md@
            Snippet 1
    ''')
    populate(snippet_infile, expected)
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)


def test_two_snippets_are_preserved(snippet_infile, snippet_outfile):
    """Writing a file preserves two snippits correctly."""
    expected = clean_text('''
        Main
          @md@
            Snippet 1
          @md@
            Snippet 2
    ''')
    populate(snippet_infile, expected)
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)


def test_nested_groups_are_handled(snippet_infile, snippet_outfile):
    """Nested sub-groups are correcttly saved."""
    expected = clean_text('''
        Main
          @md@
            Snippet 1
        Main : Subgroup
          @md@
            Snippet 2
    ''')
    populate(snippet_infile, expected)
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)


def test_nested_groups_with_tags_are_handled(snippet_infile, snippet_outfile):
    """Nested sub-groups with tags are correcttly saved."""
    expected = clean_text('''
        Main
          @md@
            Snippet 1
        Main : Subgroup [tag-a tag-b]
          @md@
            Snippet 2
    ''')
    populate(snippet_infile, expected)
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)


def test_leading_comment_block_is_preserved(snippet_infile, snippet_outfile):
    """Writing a file preserves any leading block comment."""
    expected = populate(snippet_infile, '''
        # A leading
        # comment block.
        Main
          @md@
            Snippet 1
    ''')
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)


def test_leading_blank_lines_are_preserved(snippet_infile, snippet_outfile):
    """Writing a file preserves leading blank lines.

    Snippets actually treats non-significant blank lines and comment lines as
    the same thing. Such lines are referred to as "preserved text".
    """
    expected = populate(snippet_infile, '''
        |
        # Comment
        Main
          @md@
            Snippet 1
    ''')
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)


def test_interspersed_text_is_preserved(snippet_infile, snippet_outfile):
    """Writing a file preserves leading blank lines."""
    populate(snippet_infile, '''
        Main
          @md@
            Snippet 1

        # Comment X
         Some text
          @md@
            Snippet 2
    ''')
    expected = clean_text('''
        Main
          @md@
            Snippet 1

          #! Some text
          # Comment X
          @md@
            Snippet 2
    ''')
    root, _ = load(snippet_infile.name)
    print(root.full_repr(details=True))
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)


def test_trailing_text_is_preserved(snippet_infile, snippet_outfile):
    """Writing a file preserves trailing comments, but not blank lines."""
    expected = populate(snippet_infile, '''
        Main
          @md@
            Snippet 1

        # Comment
        |
    ''')
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    expected = expected[:-1]
    assert expected == str(snippet_outfile)


def test_keywords_are_saved(snippet_infile, snippet_outfile):
    """Keywords are saved."""
    expected = populate(snippet_infile, '''
        Main
          @keywords@
            one
            two
          @md@
            Snippet 1

        # Comment
    ''')
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)


def test_title_is_preserved(snippet_infile, snippet_outfile):
    """An user supplied title is saved."""
    expected = populate(snippet_infile, '''
        @title: User supplied title
        Main
          @keywords@
            one
            two
          @md@
            Snippet 1

        # Comment
    ''')
    root, title = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert 'User supplied title' == title
    print(str(snippet_outfile))
    assert expected == str(snippet_outfile)


def test_keywords_can_be_on_marker_line(snippet_infile, snippet_outfile):
    """Keywords can be listed on the same line as the marker."""
    populate(snippet_infile, '''
        Main
          @keywords@ one two
          @md@
            Snippet 1
    ''')
    expected = clean_text('''
        Main
          @keywords@
            one
            two
          @md@
            Snippet 1
    ''')
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)


def test_keywords_can_be_on_same_line(snippet_infile, snippet_outfile):
    """Keywords can be listed on a line as well as singly."""
    populate(snippet_infile, '''
        Main
          @keywords@
            one two
            zeta
          @md@
            Snippet 1
    ''')
    expected = clean_text('''
        Main
          @keywords@
            one
            two
            zeta
          @md@
            Snippet 1
    ''')
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)


def test_all_keywords_are_collected(snippet_infile, snippet_outfile):
    """Keywords in multipls places are aggregated."""
    populate(snippet_infile, '''
        Main
          @keywords@ one two
            zeta
          @md@
            Snippet 1
          @keywords@
            alpha two
    ''')
    expected = clean_text('''
        Main
          @keywords@
            alpha
            one
            two
            zeta
          @md@
            Snippet 1
    ''')
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)


def test_groups_are_aggregated(snippet_infile, snippet_outfile):
    """Multiple goups with the same name are aggregated into one group."""
    populate(snippet_infile, '''
        Main
          @md@
            Snippet 1
        Main
          @md@
            Snippet 2
        Second
          @text@
            Snippet 4
        Main
          @md@
            Snippet 3
    ''')
    expected = clean_text('''
        Main
          @md@
            Snippet 1
          @md@
            Snippet 2
          @md@
            Snippet 3
        Second
          @text@
            Snippet 4
    ''')
    root, _ = load(snippet_infile.name)
    save(snippet_outfile.name, root)
    assert expected == str(snippet_outfile)
