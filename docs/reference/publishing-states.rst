.. ref-publishing-states:

====================
Publishing states
====================

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
until a deletion request is made.
