from pygments.lexer import RegexLexer, bygroups
from pygments.token import *


Group = Name.Variable
Tag = Name.Label
Bracket = Text
Marker = Name.Attribute
At = Name.Decorator


class CustomLexer(RegexLexer):
    name = 'snippets'
    aliases = []
    filenames = ['*.snip']

    tokens = {
        # This state is (re)entered at the start of a line.
        'root': [
            # A blank line is skipped.
            (r'(?x) \s * \n', Text),

            # A comment starts with a hash '#'.
            (r'(?x) \# .* \n', Comment),

            # Spaces at the start of the line means not a group. Specifically
            # 2 spaces means we expect a marker, 4 spaces means expect body
            # text.
            (r'(?x) \s {2} (?= \S)', Text, 'marker'),
            (r'(?x) \s {4} (?= \S)', Text, 'body'),
            (r'(?x) \s +', Text, 'body'),

            # ... otherwise we are probably processing a group.
            (r'(?x) (?=.)', Text, 'group'),
        ],

        'group': [
            # A top level directive.
            (r'(?x) (@) (\w+) (:) (.* \n)',
                bygroups(At, Marker, Text, String.Doc)),

            # Skip over colons.
            (r'(?x) : \s*', Text),

            # A (sub)group name is composed of printable characters and and
            # continues to a colon, end of the line or an opening bracket.
            (r'(?x) [^:[\n] + \s* (?=:)', Group),
            (r'(?x) [^:[\n] + \s* (?=\[)', Group,  'tags'),
            (r'(?x) [^:[\n] + \s* \n', Group, '#pop'),
        ],

        'tags': [
            # There is an opening bracket to consume when we enter this state.
            #(r'(?x) \[', Name.Class),
            (r'(?x) \[', Bracket),

            # White space is ignored.
            (r'(?x) \s', Text),

            # Tags are are sequences of word characters.
            (r'(?x) \w+', Tag),

            # Identify end of tags.
            (r'(?x) \] .* \n', Bracket, '#pop:2'),
            (r'(?x) \W.* \n', Text, '#pop:2'),
        ],

        'marker': [
            # A marker is an identifier surrounded by '@' symbols.
            (r'(?x) (@) (\w+) (@) (.* \n)',
                bygroups(At, Marker, At, Text)),

            # A comment starts with a hash '#'.
            (r'(?x) \# .* \n', Comment, '#pop'),

            # Otherwise we just have content.
            (r'(?x) .*\n', Text, '#pop'),
        ],
        'body': [
            # Treat anything as just content.
            (r'(?x) .*\n', Text, '#pop'),
        ],
    }
