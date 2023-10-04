==================================
Welcome to Clippets' documentation
==================================

Introduction
============

Clippets is a Terminal User Interface (TUI) application designed make it easy
to build up *rich* text within your computer's clipboard, by selecting text
snippets from a organised collection. You can view this short `video`_ to get
the basic idea.

Clippets was developed to support people such as teachers who often find they
make the same comments many times when marking student papers. It tries to
making finding and selecting text snippets fast and easy.


Features
--------

- Text snippets may be written using Markdown syntax, which is converted to
  suitably marked up text when pasted into Word or LibreOffice Writer.

- Text snippets are organised into a nested hierarchy of groups to make
  navigating to the desired snippet easy.

- User defined keywords are highlighted to make desired snippets easier to
  spot.

- Groups may be given tags. Groups with the same tag can be folded or expanded
  with a single mouse click.

- A collection of snippets is stored in a text file, intended to be directly
  editable by the user.

  - Clippets watches for changes to this file and allows them to be loaded
    without restarting.

  - You can also use the built-in or an external editor to add or change
    snippets.

- The group and snippet hierarchy can be reorganised within the TUI.

- Full keyboard support, plus mouse support for many operations.



Table of contents, indices and tables
=====================================

.. toctree::
   :maxdepth: 2

   getting-started/main
   user-guide/main
   reference/main

- :ref:`genindex`
- :ref:`search`

.. include:: credits.txt


.. _video: https://github.com/paul-ollis/snippets/assets/6062510/acc93396-c7b8-429f-825e-cfd940959760
