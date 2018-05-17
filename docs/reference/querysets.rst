.. ref-querysets:

========================
Publisher querysets
========================


Publisher includes a Manager that provides a number of useful querysets. These can be used for
example::

  Poll.objects.publisher_published()


``publisher_published``
.......................

Returns only published objects: ``filter(publisher_is_published_version=True)``


``publisher_drafts``
....................

Returns only draft objects: ``filter(publisher_is_published_version=False)``


``publisher_pending_deletion``
..............................

Returns objects pending deletion::

  filter(
      publisher_is_published_version=True,
      publisher_deletion_requested=True,
      )


``publisher_pending_changes``
.............................

Returns objects that have a published version, and a draft with changes::


    filter(
        Q(publisher_is_published_version=False) |
        Q(
            publisher_is_published_version=True,
            publisher_draft_version__isnull=False,
        )
    )


``publisher_draft_or_published_only(prefer_drafts=False)``
..........................................................

For example::

  Poll.objects.publisher_draft_or_published_only(prefer_drafts=True)

See ``models.py`` for details of how this is implemented.

Guarantees that for each item, you get one and only only one database object back, and gives you
the option of preferring either the draft or published version if both exist.

For convenience, these two options are also available as::

    publisher_draft_or_published_only_prefer_drafts

    publisher_draft_or_published_only_prefer_published
