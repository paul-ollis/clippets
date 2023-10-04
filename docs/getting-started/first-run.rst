Run Clippets
------------

Clippets needs a file to hold your snippets, here we assume is it called
``snippets.txt`` and does not already exist. Run Clippets using one of the
following commands [#why_snippets]_:

.. code-block::

   clippets snippets.txt
   snippets snippets.txt

The first time you run this command Clippets will create a minimal snippet hierarchy
and offer to create the file.

.. image:: first-run/first-run.svg

Click on the 'Create' button or just press the 'Enter' key. Then press the
following keys:

1. Enter
#. Down
#. Down
#. Enter

Your terminal should look like:

.. image:: first-run/basics.svg

Open or switch to a word processor program and perform a paste operation (for
example by typing ``Control+V``). The 2 snippets you chose should be pasted
into your document.


Where next
~~~~~~~~~~

The ``F1`` key will bring up a help screen to give you a brief summary of how
to use Clippets.

The :ref:`User guide <user-guide>` provides detailed information on how to make
progress with Clippets.

----

.. [#why_snippets]
    The prototype version of Clippets was called '"Snippets", but that name was
    not available in `PyPi`_.

.. _PyPi: https://pypi.org/
