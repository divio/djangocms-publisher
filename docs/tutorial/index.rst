.. _tutorial:

========
Tutorial
========

In this example we will use:

* the latest version of django CMS
* django CMS Publisher
* the `Django Polls application <https://github.com/divio/django-polls>`_

The same principles can be used to integrate django CMS Publisher into any other application.


Set up the project
==================

Set up the project locally::

  divio project setup <slug>

In the project's ``addons-dev`` directory, clone django CMS publisher and Django Polls::

  git clone git@github.com:divio/djangocms-publisher.git
  git clone git@github.com:divio/django-polls.git

Add both to the ``INSTALLED_APPS``::

  INSTALLED_APPS.extend([
      "djangocms_publisher",
      "polls",
  ])

Run migrations::

  docker-compose run --rm web python manage.py migrate

You should see the ``polls.0001_initial`` migration being applied.

In the project's ``urls.py``, add the URL configuration for polls::

  urlpatterns = [
      url(r'^polls/', include('polls.urls', namespace='polls')),
  ] + aldryn_addons.urls.patterns() + i18n_patterns(
      # add your own i18n patterns here
      *aldryn_addons.urls.i18n_patterns()  # MUST be the last entry!
  )

Start the project::

  docker-compose up

Add a couple of polls at http://localhost:8000/en/admin/polls/poll/add/.

And check that you can see them at http://localhost:8000/polls/.


Configure models for Publisher
=================================================================

Fields
------

In the ``models.py`` of polls, import the necessary modules::

  from djangocms_publisher.models import PublisherModelMixin


And change the ``Poll`` class, which must now be a ``PublisherModelMixin`` sub-class::

  class Poll(PublisherModelMixin):

This adds new fields to the ``Poll`` model, so create and run migrations::

  docker-compose run --rm web python manage.py makemigrations
  docker-compose run --rm web python manage.py migrate

The new fields on ``Poll``:

- ``publisher_deletion_requested``
- ``publisher_is_published_version``
- ``publisher_published_at``
- ``publisher_published_version``


Methods
-------

In order to manage publishing, Publisher must copy instances of ``Poll``.

For example, when an object is published for the first time, what actually happens behind the
scenes is that a new ``Poll`` instance - a database row - is created as a copy of the draft (see
the Reference section below for more details of what happens in these operations).

Since Each ``Poll`` has several ``Choices`` (they each have a foreign key to their ``Poll``) we
need to handle these relations too (i.e. the related ``Choice`` objects must be copied too).

To handle this, we use the ``publisher_copy_relations`` method::

  def publisher_copy_relations(self, old_obj):

      # If there are any Choices currently pointing to the new version (self), we should delete
      # them from the source object (old_obj), so we don't end up with duplicates.

      self.choice_set.all().delete()

      # loop over the Choices pointing at the source object
      for choice in old_obj.choice_set.all():
          # copy each one, point it at the right Poll, and save
          choice.pk = None
          choice.poll = self
          choice.save()


Configure admin for Publisher
=============================

In the ``admin.py`` of Django Polls, import the admin class mixin, and modify the ``PollAdmin``
class to use it::

  from djangocms_publisher.admin import PublisherAdminMixin

  [...]

  class PollAdmin(
      PublisherAdminMixin,
      admin.ModelAdmin
      ):


Using the publishing functionality in the admin
-----------------------------------------------

This is basic minimum implementation of publishing functionality.

You can test it by visiting http://localhost:8000/en/admin/polls/poll/.

Each poll now has new controls alongside the familiar **Save** button (you won't see them all at
once though):

* **Publish** - available when a draft is extant
* **Edit** - available when a published version is extant, in *Published* view
* **View published version** - available when a published version is extant, in *Draft* view


Refinements
-----------

The implementation is extremely basic. If you have a ``Poll`` with both draft and published
versions extant, you'll find that it appears twice in the admin list; the same goes for ``Choice``
- we display the choices appertaining to both draft and published versions.

The solution for the ``Polls`` changelist is to overwrite its ``get_changelist`` method::

    def get_changelist(self, request, **kwargs):

         ChangeList = super(PollAdmin, self).get_changelist(request, **kwargs)

         class DraftOrLiveOnlyChangeList(ChangeList):
             def get_queryset(self, request):
                 return (
                     super(DraftOrLiveOnlyChangeList, self)
                     .get_queryset(request)
                     .publisher_draft_or_published_only_prefer_published()
                 )
         return DraftOrLiveOnlyChangeList

The solution for the choices is a bit different. The are various ways to approach this, but in this
case, it seems reasonable that since each ``Choice`` only makes sense in the context of its
``Poll``, and can already be edited their as an inline, we will restrict editing of ``Choices`` to
that - there will no longer be a ``Choices`` changelist.

To do this, delete ``admin.site.register(Choice)``.

The admin list could also be more informative. It doesn't tell us anything about the states of the
objects.

Edit the ``list_display``::

    list_display = (
        'question',
        'publisher_is_published_version',
        'publisher_state',
    )

This provides more information, showing whether the object is published at all, and whether a draft
exists.


Configure views for Publisher
========================================

We have an issue in the list of polls at http://localhost:8000/polls/: if a Poll has
``Poll`` objects for both draft and published states, it will show up twice in the list.

That's because we do::

  def get_queryset(self):
      return Poll.objects.all()[:5]

in the ``IndexView``. We should be more discriminating::

  def get_queryset(self):
      return Poll.objects.publisher_published()[:5]


Notes on the tutorial
=====================

This is a the most basic possible introduction to django CMS Publisher. More needs to be done for a
viable application. For example, although draft Polls are hidden in the list, they are still
accessible to a user who manipulates the URL.

See ``/test_project/test_app`` for more implementation examples that you can adopt for a real
project.
