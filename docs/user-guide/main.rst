.. _user-guide:

==========
User guide
==========

.. toctree::
   :maxdepth: 2

   basics
   groups
   editing
   moving
   finding
   external-editor
   backups

..  Things to cover.

    - Markdown vs plain snippets.
    - A good link for basic Markdown.
    - Using the help.
    - Deleting groups.
    - Editing tags.

..  Things we cannot do.

    - Add a snippet of a given type / change snippet type.
    - Use simple text search in the filter field.
    - Should re-gaining focus update the clipboard.
    - Snippet ordering should be shown next to the clipboard widget.
    - Consider something different to ``Ctrl-Q`` for quitting the editor.
    - I think that 'added snippet highlighting' disappears after using the
      internal editor on the clipboard. This appears deliberate, but feels
      counter-intuitive.
    - PgUp and PgDn should do something useful.


.. RST syntax highlighting bugs.

    - For ``marking.snip``,

      The trailing comment is part of the literal text.

    - For :ref:`folding`)

      The trailing ')' is part of the interpreted text.

    - In, for example :refnum:`components`

      Spell checking is not disabled.
