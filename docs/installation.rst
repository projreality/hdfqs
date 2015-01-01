.. _installation:

Installation
============

HDFQS can be installed either via :command:`pip`, cloning the git repository, or downloading the source distribution.

Installing via pip
------------------

Run either as root, or with :command:`sudo`::

  pip install hdfqs

Installing from git repository
------------------------------

Inside the git repository, run::

  python setup.py install

Installing from source distribution
-----------------------------------

Extract the source distribution file (replace [VERSION] with the actual version) and install::

  tar -xvf hdfqs-[VERSION].tgz
  cd hdfqs-[VERSION]
  python setup.py install

Usage
-----

In python, import the module as::

  import hdfqs;

or::

  from hdfqs import HDFQS;

