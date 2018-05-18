.. _documentation:

=======================
About the documentation
=======================

This documentation is `automatically published on Read the Docs
<https://divio-djangocms-publisher.readthedocs-hosted.com/en/latest/>`_ and updated there
when commits are made to the ``develop`` branch of `django CMS Publisher GitHub repository
<https://github.com/divio/djangocms-publisher>`_.

The documentation is written in RST and built using Sphinx.


Building the documentation locally
==================================

In the repository's ``docs`` directory, run::

   * make install   # creates a virtual environment named env in the docs directory

Then::

  * make html       # build the documentation
  * make run        # build the documentation and serve it at http://localhost:8001/

To check spelling::

  * make spelling


Documentation standards
=======================

Page titles::

  ==========
  Page title
  ==========

Heading::

  Headings
  ========

  Sub-headings
  ------------

  Sub-sub-headings
  ~~~~~~~~~~~~~~~~

  Sub-sub-sub-headings
  ^^^^^^^^^^^^^^^^^^^^

  Sub-sub-sub-sub-headings
  ........................
