===============
PyDev Formatter
===============


.. image:: https://img.shields.io/pypi/v/pydevf.svg
        :target: https://pypi.python.org/pypi/pydevf

.. image:: https://img.shields.io/travis/fabioz/pydevf.svg
        :target: https://travis-ci.org/fabioz/PyDev.Formatter


Features
==========

This package provides a command line API to use the PyDev Code Formatter (the PyDev
Code formatter is created by extracting the engine for code formatting provided by
PyDev: http://www.pydev.org).

The PyDev Formatter is a conservative python code formatter and will try to keep the 
structure of the code as close as possible to the original sources, while fixing many
common issues such as:

- Keep a space after commas
- Trim spaces inside parenthesis
- Right-trim lines
- Add a space before and after operators
- Keep 2 lines before top level classes/methods
- Keep 1 line before inner classes/methods
- Add new line at end of file
- Format comments to have 2 spaces before a comment and 1 space inside the comment

Note that it does not try to break statements to fit any pre-specified line length (as gofmt).

Command line
=============

Basic use of the formatter is:
 
``python -m pydevf <filename_or_directory>``

``python -m pydevf -h`` may be used to see the help for additional parameters.

Installing
============

Requisites
-----------

- java 8+ (so, make sure java is installed and in your PATH)
- python 2.7 or 3.4 onwards
- click 6+

Install with pip
-----------------

To install the PyDev Formatter use:

``pip install pydevf``

Using with pre-commit
---------------------

To use it with `pre-commit`_, just add the following repo to your ``.pre-commit-config.yaml``::

    -   repo: https://github.com/fabioz/PyDev.Formatter
        rev: ''  # Use the sha or tag you want to point at
        hooks:
        -   id: pydevf

.. _pre-commit: https://pre-commit.com/

Dealing with big lines
========================

Note that in PyDev there are tools to help on those manual cases. i.e.:

Wrap docstrings/comments with ``Ctrl+2, W`` -- See: http://pydev.blogspot.com/2015/04/wrapping-docstringscomments-in-pydev.html.

Wrap/unwrap lists/calls with ``Ctrl+1``, ``Wrap expression``/``Unwrap expression`` (used with cursor inside the list/call).

Daemon mode
============

By default the formatter will create a daemon and will reuse it among multiple invocations (because
the formatter is **very fast** but its startup is slow). If you don't want to use this mode use
the ``--no-daemon`` parameter. 

License
==========

* EPL (Eclipse Public License) 2.0

Releasing
==========

- Update versions on ``setup.py`` and ``version.py``
- ``git tag {{version}}`` (i.e.: v0.1.2)
- ``git push --tags`` (travis should build and deploy)

Local release
---------------

- Update versions on ``setup.py`` and ``version.py``
- ``python setup.py sdist bdist_wheel``
- ``python -m twine upload dist/*``
