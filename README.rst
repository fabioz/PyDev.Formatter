===============
PyDev Formatter
===============


.. image:: https://img.shields.io/pypi/v/pydevf.svg
        :target: https://pypi.python.org/pypi/pydevf

.. image:: https://img.shields.io/travis/fabioz/pydevf.svg
        :target: https://travis-ci.org/fabioz/PyDev.Formatter

.. image:: https://readthedocs.org/projects/pydevf/badge/?version=latest
        :target: https://pydevf.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status



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

And will not try to break statements to fit any pre-specified line length (as gofmt).

Command line
=============

To use the formatter use:
 
`python -m pydevf <filename_or_directory>`

`python -m pydevf -h` may be used to see the help for additional parameters.

Installing
============

Requisites
-----------

- java 8+ (so, make sure java is installed and in your PATH)
- python 2.7 or 3.4 onwards
- click 6+

Install with pip
-----------------

`pip install pydevf` should be used to install the PyDev Formatter.

Dealing with big lines
========================

Note that in PyDev there are tools to help on those manual cases. i.e.:

Wrap docstrings/comments with `Ctrl+2, W` -- See: http://pydev.blogspot.com/2015/04/wrapping-docstringscomments-in-pydev.html.

Wrap/unwrap lists/calls with `Ctrl+1`, `Wrap expression`/`unwrap expression` (used with cursor inside the list/call).

Daemon mode
============

By default the formatter will create a daemon and will reuse it among multiple invocations (because
the formatter is **very fast** but its startup is slow). If you don't want to use this mode use
the `--no-daemon` parameter. 

License
==========

* EPL (Eclipse Public License) 2.0

Releasing
==========

- Update versions on setup.py and version.py
- python setup.py sdist bdist_wheel
- python -m twine upload dist/*
