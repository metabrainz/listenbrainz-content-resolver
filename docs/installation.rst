.. _installation:

Installation
============

Installation for End Users
--------------------------

Run pip, yo!

Installation for Development
----------------------------

Linux and Mac
^^^^^^^^^^^^^

Use these command line arguments to install Troi on Linux and Mac:

.. code-block:: bash

    virtualenv -p python3 .ve
    source .ve/bin/activate
    pip3 install .[tests]
    python3 -m troi.cli --help

Windows
^^^^^^^

Use these commands to install on Windows:

.. code-block:: bash

    virtualenv -p python .ve
    .ve\Scripts\activate.bat
    pip install .[tests]
    python -m troi.cli --help

