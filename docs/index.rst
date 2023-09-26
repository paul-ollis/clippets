==================================
Welcome to Clippets' documentation
==================================


Introduction
============

Clippets is a terminal user interface (TUI) application designed make very easy
to build up *rich* text within your computer's clipboard, by selecting text
snippets from a organised collection. You can view this short video_ to get the
basic idea.

Clippets was developed to support people such as teachers who often find they
make the same comments many times when marking student papers. It tries to making
finding and selecting text snippets fast and easy.


Features
--------

- Text snippets may be written using Markdown syntax, which is converted to
  suitably marked up text when pasted into Word or LibreOffice Writer.

- Text snippets are organised into a nested hierarchy of groups to make
  navigating to the desired snippet easy.

- User defined keywords are highlighted to make desired snippets easier to spot.

- Groups may be given tags. Groups with the same tag can be folded or expanded
  with a single mouse click.

- A collection of snippets is stored in a text file, intended to be directly
  editable by the user.

  - Clippets watches for changes to this file and allows them to be loaded
    without restarting.

  - Alternatively, you can use the built-in or an external editor to add or
    modify snippets.

- The group and snippet hierarchy can be reorganised within the TUI.

- Full keyboard support and the mouse can also be used for many operations.


Credits
=======

Clippets would have been much harder to write without `Textual`_ as the
application framework.

I am also heavily indebted to Ted Conbeer for his `textual-textarea widget`_,
which provided much of the code for Clippets' built in editor.



Table of contents, Indices and tables
=====================================

.. toctree::
   :maxdepth: 2

   file_format

- :ref:`genindex`
- :ref:`search`


.. _Textual: https://textual.textualize.io
.. _video: https://github.com/paul-ollis/snippets/assets/6062510/acc93396-c7b8-429f-825e-cfd940959760
.. _`textual-textarea widget`: https://github.com/tconbeer/textual-textarea
