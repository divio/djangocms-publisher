# Django Drafts

A toolkit to build draft/live version support for Addons.
With django-drafts support your app will have a draft version of
objects that can then be published to the live version. Only the live
version is visible to visitors. Permissions can be set for who is
allowed to publish a draft.

Optionally integrates with the django CMS Toolbar.

## Integration

django-drafts follows a loose integration model. It defines some basic
conventions on how draft/live logic can be implemented and provides
helpers, mixins and hints.

Add ``django-drafts`` as a dependency of your package.

- [ ] Basic model support
- [ ] admin actions for publishing
- [ ] permissions
- [ ] django-cms toolbar
- [ ] Integrating django-parler
- [ ] aldryn-newsblog sample integration
- [ ] django-filer integration (optional. off by default)
