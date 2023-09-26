Linux
-----

Make sure Python is installed using your distribution's package manager. You
should then be able to install Clippets using "pip".

.. code-block::

   python -m pip install --user clippets

If the above does not work, you may need to run:

.. code-block::

   python -m pip ensurepip

If this indicates that your distribution blocks "ensurepip" for the system
installation of Python, consider using a virtual environment (see
`https://docs.python.org/3/library/venv.html for more details`).

.. code-block::

   python -m venv clippets

   # Activate (assuming you are using Bash). See above link for other shells.
   source clippets/bin/activate

   python -m pip install clippets
