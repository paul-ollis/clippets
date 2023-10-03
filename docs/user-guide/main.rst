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
    - When all groups are folded, the 'right' key moves off the selected group,
      which should not be allowed.
    - Snippet moving does not cope with collapsed groups.
    - An empty snippet does not render properly. It needs to be a proper blank
      line.
    - The help page is woefully out of date.
    - Cancelling add-snippet still adds a snippet to the tree, but does not add
      a widget. Causes a crash.
    - PgUp and PgDn should do something useful.
    - Does the context menu show ``Move`` when snippet movement is not possible.
      Yes it does. It should be greyed out.
    - Should all snippet place-holders be made visible during snippet moving to
      be consistent with group moving?


.. RST syntax highlighting bugs.

    - For ``marking.snip``,

      The trailing comment is part of the literal text.

    - For :ref:`folding`)

      The trailing ')' is part of the interpreted text.

    - In, for example :refnum:`components`

      Spell checking is not disabled.
