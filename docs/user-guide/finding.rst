.. _finding:

================
Finding snippets
================

In order for Clippets to be as useful as possible, you need to be able to find
the snippet you want as quickly as possible. Clippets' user interface is
designed with this aim in mind [#helpme]_. The features, discussed elsewhere,
that are intended to make finding snippets efficient are:

- Hierarchical and foldable groups; see :ref:`folding`.
- Marking related groups using tags; see :ref:`folding`.

This section covers the following additional features.

- Keywords.
- The search tool.

Keywords
========

Keywords are intended to make it easier to spot the snippet you want. Every
group can have an associated set of keywords. See :ref:`editing` for how set
the keywords for a group. Each keywords is shown highlighted using a different
colour, up to 10 colours; (for more than 10 keywords the colours start to get
reused).

.. figure:: basics/keywords.svg

    A number of highlighted keywords.


Search tool
===========

.. _search:
.. figure:: basics/searching.svg

    An example of searching for snippets.

.. sidebar:: Regular expressions

    These are very powerful, but also complex and a big subject. See `py_regex`_
    for the full, gory details of the regular expression 'flavour' used by
    Clippets.

    In regular expressions many punctuation characters have special meanings;
    for example a plain asterisk (``'*'``) will not match asterisk characters in
    your snippets. So if you are not experienced with *regular expressions* and
    do not want to get confused, avoid using punctuation characters.

    Certain punctuation characters do not have special meanings and can be
    safely used. Safe characters include ``'#'``, ``'@'``, comma, single and
    double quotes.

    One special character you might find useful is the vertical bar (or pipe)
    symbol. This allows you to specify several difference pieces of text, any
    one of which can match a snippet. This is shown in :numref:`search`.

At the top of the Clippets display is a search/filter box. You can press
``control-f`` or click on the box to edit its contents. As you type into this
box the snippet tree is filtered so only show those snippets that contain the
search text you have entered. Groups containing no match are shown as empty,
but notice that they are not shown as folded unless that are actually folded.

The above figure shows the search box being uses to find all the snippets that
contain either 'spelling' or 'grammar'. This is possible because Clippets
typically treats the search expression as a *regular expression* rather than a
simple piece of text to match.

If you are familiar with *regular expressions* then there is a good chance that
you either love them or hate them. If they are new to you then the side bar
gives a very quick primer and how to avoid them [#re]_.

If the text you type into the search box is not a valid regular expression then
Clippets falls back to doing a simple text search.

----

.. [#helpme]
    But I am keen to receive ideas on how to make Clippets more user friendly.

.. [#re]
    Clippets should soon be updated soon to allow searching using just plain
    text.

.. _py_regex: https://docs.python.org/3/library/re.html#regular-expression-syntax
