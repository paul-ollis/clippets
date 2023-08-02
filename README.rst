Clippets
========

A terminal based tool to quickly combine (rich) text snippets into the
clipboard.

https://github.com/paul-ollis/snippets/assets/6062510/acc93396-c7b8-429f-825e-cfd940959760

Clippets s a Textual (https://textual.textualize.io/) framework based application.


Status
======

This is a *beta* software. I believe that it is useful and usable in its current
form:

- It performs its basic function and provides a user interface that is good
  enough to support productive use.
- It has a fairly comprehensive test suite.
- I hope that crashes should be rare (backup files are maintained to minimise
  the impact).

However:

- It still needs more tests.
- There are areas of mouse and keyboard support that beg improvement.
- Some desirable features are obviously missing, such as:

  - There is no proper documentation beyound the built-in help.
  - It does not yet work on MacOS.


Getting started
===============

Windows installation
--------------------

Install Python
~~~~~~~~~~~~~~

You will need Python, which you can download from www.python.org.

- Choose the latest version (currently 3.11)
- When you install select the following additional options, when prompted:

  - Add Python to environment variables.
  - Precompile standard library.


Extra Python configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~

Now add the Python script directory to your PATH as follows:

- Open a Command Promp (type 'cmd' in the Windows search box to find the Command
  Prompt app).

- At the prompt enter this command:

  .. code::

     python -c "import sys; print(sys.executable)"

  This show where Python is installed. On my PC this displays:

  .. code::

     c:\Users\Paul\AppData\Local\Programs\Python\Pytheon311\python.exe

- Type 'environment' in the Windows search box. The open "Edit the system
  environment variables, Control panel".

  - Click on the "Environment Variables" near the bottom or the "System
    Properties" window.

  - In the "Environment Variables" window, find "Path" entry, select it and
    click the "Edit..." button below.

  - In the "Edit Environment Variable" window, click the "New" button and enter
    the Python scripts path, based on the Python installation directory obtained
    earlier. In my case the path I need is:

    .. code::

       c:\Users\Paul\AppData\Local\Programs\Python\Pytheon311\Scripts

    *i.e.* replace "python.exe" with "Scripts".A

 - Click OK and close all the windows opened so far, including the "Command
   Prompt" window.


Install Windows Terminal (highly recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Clippets will run in a standard windows terminal, but you will get much better
results (such as italic text, better colours, included the excellent Cascadia
fonts) if you install "Windows Terminal", which is readily available in the
Microsoft App store.

After you have installed Windows Shell, I highly recommend that you make it the
default for command line tools. (I am not aware of any good reason to keep using
the old console.)

- Enter "terminal host" in the Windows search box and run "Choose a terminal
  host app for interactive command-line tools".

- Scroll down (if necessary) to the "Terminal" secion and make sure that
  "Windows Console Host" is selected.


Install Clippets
~~~~~~~~~~~~~~~~

- Open a new Command Promp (type 'cmd' in the Windows search box to find the
  Command Prompt app).

- Enter the command:

  .. code::

     python -m pip install --user clippets

This will install the Clippets application.


Linux
-----

Make sure Python is installed using your distribution's package manager. You
should then ba able to install clippets using "pip".

.. code::

   python -m pip install --user clippets

If the above does not work, you may need to run:

.. code::

   python -m pip ensurepip

If this indicates that your distribution blocks "ensurepip" for the system
insallation of Python, consider using a virtual environment (see
https://docs.python.org/3/library/venv.html for more details).

.. code::

   python -m venv clippets

   # Activate (assuming you are using Bash). See above link for other shells.
   source clippets/bin/activate

   python -m pip install clippets


Running clippets/snippets
-------------------------

You will first need a minimal file containing snippets. For example:

.. code::

  Main
    @md@
      My *first* snippet

You can name the file as you want. Let's assume the file is called
'snippets.txt'. Run clippets as one of the following commands:

.. code::

   snippets snippets.txt
   clippets snippets.txt

The ``F1`` key will bring up a help screen to get you going.
