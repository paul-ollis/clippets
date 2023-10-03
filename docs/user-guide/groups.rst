.. _folding:

==================
Groups and folding
==================

Groups allow you to collect related snippets together into a tree hierarchy,
parts of which can be folded so you can easily see a useful subset of your
snippets. The figure below shows Clippets with a partially folded tree.

.. figure:: groups/folded.svg

    An example of folded groups.

Folded groups have start with a closed triangle (``▶``) symbol and unfolded
groups start with an open triangle (``▽``) symbol. The folded state of groups
may be toggled in a number of ways.


.. rubric:: The ``F9`` key.

This toggles between having all groups folded and all unfolded. If any group is
not folded when this is pressed the all groups will become folded, as shown below.

.. figure:: groups/all-folded.svg

    All groups folded.

If all groups are folded then ``F9`` will unfold all groups, recursively. ``F9``
is useful when you only want a few select folds to be open.


.. rubric:: Left click on a group.

Left clicking on a group name simply toggles the folded state of the group.


.. rubric:: Keyboard group selection.

Pressing the ``left`` key will change the keyboard selection from 'snippet
selection mode' to 'group selection mode', which looks like this:

.. figure:: groups/group-mode.svg

    Group selection mode.

.. todo::
    There is some duplication here WRT user-guide/basics.rst

When in group mode, the ``up`` and ``down`` keys move between group labels and
pressing either ``f`` or the ``Ins`` key [#ins]_ will toggle the folded state
of the selected group.

The ``right`` key will move back to 'snippet selection mode' provided the
selected group is unfolded.


.. rubric:: Tags

The tags listed after group labels ('rigour', 'style' and 'para' in these
examples) allow multiple groups to be folded/unfolded at once. Simply click on
one of the tag labels using the left mouse button. The figure below shows the
effect of clicking on the 'para' tag.

.. figure:: groups/para-fold.svg

    The effect of folding using the 'para' tag.

The ``F9`` key in combination with group tags provides a mechanism for quickly
getting just a few open folds.

----

.. [#ins]
    The insert (``Ins``) key is typically close to the arrow keys on the
    keyboard, so this key is convenient when opening and closing folds.
