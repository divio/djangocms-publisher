django CMS Publisher
====================

Introduction
------------

django CMS Publisher provides publishing control to models in existing applications.

By default, any saved changes to a model published instantly. django CMS Publisher extends an
application's models so that they exist in *draft* and *published* states, allowing users to work
on unpublished drafts, whether a published version exists yet or not, and publish changes when they
are ready.

:doc:`tutorial`


Tutorial: integrate django CMS Publisher into an existing application
---------------------------------------------------------------------

In this example we will use:

* the latest version of django CMS
* django CMS Publisher
* the `Django Polls application <https://github.com/divio/django-polls>`_

The same principles can be used to integrate django CMS Publisher into any other application.


Set up the project
^^^^^^^^^^^^^^^^^^

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


Add basic django CMS Publisher support to Django Polls
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Models
~~~~~~

Fields
......

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
.......

In order to manage publishing, Publisher must copy instances of ``Poll``. For example, when an
object is published for the first time, what actually happens behind the scenes is that a new
``Poll`` instance - a database row - is created as a copy of the draft (see the Reference section
below for more details of what happens in these operations).

Since Each ``Poll`` has several ``Choices`` (they each have a foreign key to their ``Poll``) we
need to handle these relations too (i.e. the related ``Choice`` objects must be copied too).

To handle this, we use the ``publisher_copy_relations`` method::

  def publisher_copy_relations(self, old_obj):

      # If there are any Choices currently pointing to the new version (self), we should delete
      # them from the source object (old_obj), so we don't end up with duplicates.
      #
      # See Handling relations in the Background section for more details why.

      self.choice_set.all().delete()

      # loop over the Choices pointing at the source object
      for choice in old_obj.choice_set.all():
          # copy each one, point it at the right Poll, and save
          choice.pk = None
          choice.poll = self
          choice.save()


Admin
~~~~~

In the ``admin.py`` of Django Polls, import the admin class mixin, and modify the ``PollAdmin``
class to use it::

  from djangocms_publisher.admin import PublisherAdminMixin

  [...]

  class PollAdmin(
      PublisherAdminMixin,
      admin.ModelAdmin
      ):


Using the publishing functionality in the admin
...............................................

This is basic minimum implementation of publishing functionality.

You can test it by visiting http://localhost:8000/en/admin/polls/poll/.

Each poll now has new controls alonsgide the familiar **Save** button (you won't see them all at once though):

* **Publish** - available when a draft is extant
* **Edit** - available when a published version is extant, in *Published* view
* **View published version** - available when a published version is extant, in *Draft* view


Refinements
...........

The implementation is extremely basic. If you have a ``Poll with both draft and published versions
extant, you'll find that it appears twice in the admin list; the same goes for ``Choice`` - we
display


How to
------

Work with translatable models
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The process for integrating Publisher with translatable models is similar to the basic method
outlined in the tutorial. The key difference is that


Reference
---------

Publishing states
^^^^^^^^^^^^^^^^^

When first created, an object has::

  id: 1
  publisher_is_published_version: False

On publishing, a new copy is created, and the original object is deleted. The new object::

  id: 2
  publisher_is_published_version: True

When a published object *without a draft* is edited, the object will be copied to a new object; there will now be a pair of objects::

  id: 2
  publisher_is_published_version: True

  id: 3
  publisher_is_published_version: False # the draft
  publisher_published_version_id: 2

This will continue to be the case until the draft object is published; at this point the
draft object is saved with the id of of the published version, and the draft object deleted::

  id: 2
  publisher_is_published_version: True

**or** until changes in the draft are discarded, in which case the draft object is deleted, **or**
until a deletion request is made <**what does this do?**>


Background
----------

Handling relations
^^^^^^^^^^^^^^^^^^
