Windows installation
--------------------

Install Python
~~~~~~~~~~~~~~

You will need Python, which you can download from `www.python.org`.

1. Choose the latest version (currently 3.11)
#. When you install select the following additional options, when prompted:

  i. Add Python to environment variables.
  #. Pre-compile the standard library.


Extra Python configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~

Now add the Python script directory to your PATH as follows:

1. Open a Command Prompt (type 'cmd' in the Windows search box to find the Command
   Prompt app).

#. At the prompt enter this command:

   .. code-block:: bat

      python -c "import sys; print(sys.executable)"

   This show where Python is installed. On my PC this displays:

   .. code-block:: bat

      c:\Users\Paul\AppData\Local\Programs\Python\Pytheon311\python.exe

#. Type 'environment' in the Windows search box. The open "Edit the system
   environment variables, Control panel".

   i. Click on the "Environment Variables" near the bottom of the "System
      Properties" window.

   #. In the "Environment Variables" window, find the "Path" entry, select it and
      click the "Edit..." button below.

   #. In the "Edit Environment Variable" window, click the "New" button and
      enter the Python scripts path, based on the Python installation directory
      obtained earlier. In my case the path I need is:

      .. code-block:: bat

         c:\Users\Paul\AppData\Local\Programs\Python\Pytheon311\Scripts

      *i.e.* replace "python.exe" with "Scripts".

   #. Click OK and close all the windows opened so far, including the "Command
      Prompt" window.


Install Windows Terminal (highly recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Clippets will run in a standard windows terminal, but you will get much better
results (such as italic text, better colours, the excellent Cascadia fonts) if
you install "Windows Terminal", which is readily available in the Microsoft App
store.

After you have installed Windows Shell, I highly recommend that you make it the
default for command line tools. (I am not aware of any good reason to keep
using the old console.)

1. Enter "terminal host" in the Windows search box and run "Choose a terminal
   host app for interactive command-line tools".

2. Scroll down (if necessary) to the "Terminal" section and make sure that
   "Windows Console Host" is selected.


Install Clippets
~~~~~~~~~~~~~~~~

- Open a new Command Prompt (type 'cmd' in the Windows search box to find the
  Command Prompt app).

- Enter the command:

  .. code-block:: bat

     python -m pip install --user clippets

This will install the Clippets application.
