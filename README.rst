.. This file is generated and will be over-written. See the Makefile and
   mk_readme.py files in docs for more details.


Clippets
========

A terminal based tool to quickly combine (rich) text snippets into the
clipboard.

`https://github.com/paul-ollis/snippets/assets/6062510/acc93396-c7b8-429f-825e-cfd940959760`

Clippets s a Textual (`https://textual.textualize.io/`) framework based application.


Status
======

This is a *beta* software. It is definitely useful and usable in its current
form:

- It performs its basic function and provides a user interface that is good
  enough to support productive use.
- It has a pretty comprehensive test suite.
- Crashes should be rare (backup files are maintained to minimise the impact).

However:

- There are areas of mouse and keyboard support that beg improvement.
- Some desirable features are obviously missing, such as:

  - There is no proper documentation beyond the built-in help.
  - It does not yet work on MacOS. (Pull requests gratefully received.)


Get started
===========

The full documentation includes instructions on installing and running Clippets
for the first time. See@

- `Windows installation`_.
- `Linux installation`_.
- `Starting Clippets`_.

.. _Windows installation: https://clippets.readthedocs.io/en/main/getting-started/windows.html
.. _Linux installation: https://clippets.readthedocs.io/en/main/getting-started/linux.html
.. _Starting Clippets: https://clippets.readthedocs.io/en/main/getting-started/first-run.html

Credits
=======

Clippets would have been much harder to write without `Textual`_ as the
application framework.

I am also heavily indebted to Ted Conbeer for his `textual-textarea widget`_,
which provided much of the code for Clippets' built in editor.

.. _Textual: https://textual.textualize.io
.. _`textual-textarea widget`: https://github.com/tconbeer/textual-textarea
