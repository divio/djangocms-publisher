Django CMS Publisher
====================

A toolkit to build draft/published support for 3rd party apps (Addons).
With djangocms-publisher support your app will have a draft version of
objects that can then be published to the live version. Only the live
version is visible to visitors. Permissions can be set for who is
allowed to publish a draft.

Optionally integrates with the django CMS Toolbar.

Integration
-----------

djangocms-publisher follows a loose integration model. It defines some
basic conventions on how draft/live logic can be implemented and
provides helpers, mixins and hints.

Add ``djangocms-publisher`` as a dependency of your package.

...
