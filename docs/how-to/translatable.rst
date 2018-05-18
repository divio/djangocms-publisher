.. how-to-translatable:

====================================
How to work with translatable models
====================================

The process for integrating Publisher with translatable models is similar to the basic method
outlined in the tutorial. The key difference is that rather than using the Publisher classes and methods for simple models, you will need to use those for Django Parler models.

For example, you will need to use the ``PublisherParlerAdminMixin`` rather than
``PublisherAdminMixin``.

An example application using these utilities can be found in ``/test_project/test_app_parler``.

..  admonition:: This section is incomplete.

    To help identify key areas for completion, please report provide feedback using `GitHub issues
    for the project <https://github.com/divio/djangocms-publisher/issues>`_.

    Pull requests for improvements are also welcome.