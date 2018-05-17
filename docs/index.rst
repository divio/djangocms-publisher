.. raw:: html

    <style>
        .row {clear: both}

        .column img {border: 1px solid black;}

        @media only screen and (min-width: 1000px),
               only screen and (min-width: 600px) and (max-width: 768px){
            .column {
                padding-left: 5px;
                padding-right: 5px;
                float: left;
                width: 25%;
            }
        }
        h2 {border-top: 1px solid black; padding-top: 1em}
    </style>


===================================
django CMS Publisher
===================================

..  warning::

    This is a work in progress.


Contents
========

.. rst-class:: clearfix row

.. rst-class:: column


:ref:`Tutorial <tutorial>`
--------------------------

Get started


.. rst-class:: column

:ref:`How-to guides <how-to>`
-----------------------------

Step-by-step guides to particular tasks


.. rst-class:: column

:ref:`Reference <reference>`
----------------------------

Technical reference


.. rst-class:: column

:ref:`Explanation <explanation>`
--------------------------------

Explanation and discussion of key topics


.. rst-class:: clearfix row

About django CMS Publisher
===================================

django CMS Publisher provides publishing control to models in existing applications.

By default, any saved changes to a model published instantly. django CMS Publisher extends an
application's models so that they exist in *draft* and *published* states, allowing users to work
on unpublished drafts, whether a published version exists yet or not, and publish changes when they
are ready.

.. toctree::
    :maxdepth: 2
    :hidden:

    tutorial/index
    how-to/index
    reference/index
    explanation/index