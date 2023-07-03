# Introduction

This is the help.


# File format

A snippets file contains a mixture of the following:

Comments
> Any unindented line that starts with a hash ('#').

One-off directives.
> Any unindented line that starts with the 'at' ('@') symbol. The currently
  recognised directives are: @title: <text>

Group plus tag names
> Any non-indended line that is not a comment. Tag names appear after the
> group name and within brackts ('[' and ']'). Tags are separated by spaces.
> The file format is basically flat, but colons (':') may be used to indicate
> nested groups. For example 'Main:Sub' defines a group 'Sub' that is a child
> of the group 'Main'.

Element start markers
> An indented line starting and ending with 'at' ('@') symbols.
> The current valid markers are: @keywords@ @md@ @text@.

Content
> Indented or blank lines that follow a start marker.

Uninterpreted
> Any other lines.
