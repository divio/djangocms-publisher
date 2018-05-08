# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.db.models import Q
from django.utils.functional import cached_property

from .publisher import Publisher


class PublisherQuerySetMixin(object):
    def publisher_published(self):
        return self.filter(publisher_is_published_version=True)

    def publisher_drafts(self):
        return self.filter(publisher_is_published_version=False)

    def publisher_pending_deletion(self):
        return self.filter(
            publisher_is_published_version=True,
            publisher_deletion_requested=True,
        )

    def publisher_pending_changes(self):
        return self.filter(
            Q(publisher_is_published_version=False) |
            Q(
                publisher_is_published_version=True,
                publisher_draft_version__isnull=False,
            )
        )

    def publisher_draft_or_published_only(self, prefer_drafts=False):
        """
        Returns a queryset that does not return duplicates of the same object
        if there is both a draft and published version.
        only a draft: include the draft
        only a published: include the published
        draft and published: include the published (the other way around if
        prefer_draft=True)

        So shorter version:
         - prefer_draft=False: exclude drafts that have a published version.
         - prefer_draft=True: exclude published versions that have a draft.
        """
        if prefer_drafts:
            return self.filter(
                # draft objects
                Q(publisher_is_published_version=False) |
                # OR published without a draft version
                Q(
                    publisher_is_published_version=True,
                    publisher_draft_version__isnull=True,
                )
            )
        else:
            return self.filter(
                # published objects
                Q(publisher_is_published_version=True) |
                # OR drafts without a published version
                Q(
                    publisher_is_published_version=False,
                    publisher_published_version__isnull=True,
                )
            )

    def publisher_draft_or_published_only_prefer_drafts(self):
        return self.publisher_draft_or_published_only(prefer_drafts=True)

    def publisher_draft_or_published_only_prefer_published(self):
        return self.publisher_draft_or_published_only(prefer_drafts=False)


class PublisherQuerySet(PublisherQuerySetMixin, models.QuerySet):
    pass


class PublisherModelMixin(models.Model):
    publisher_is_published_version = models.BooleanField(
        default=False,
        editable=False,
        db_index=True,
    )
    publisher_published_version = models.OneToOneField(
        to='self',
        blank=True,
        null=True,
        default=None,
        related_name='publisher_draft_version',
        limit_choices_to={'publisher_published_version_id__isnull': True},
        editable=False,
    )
    publisher_published_at = models.DateTimeField(
        blank=True,
        null=True,
        default=None,
        editable=False,
    )
    publisher_deletion_requested = models.BooleanField(
        default=False,
        editable=False,
        db_index=True,
    )

    objects = PublisherQuerySet.as_manager()

    class Meta:
        abstract = True

    @cached_property
    def publisher(self):
        return Publisher(instance=self, name='publisher')

    # USER OVERRIDABLE
    publisher_copy_object_exclude_fields = ()

    def publisher_copy_relations(self, old_obj):
        # At this point the basic fields on the model have all already been
        # copied. Only relations need to be copied now.
        # If this was a django-parler model, the translations will already
        # have been copied. (but without their relations, that is also up to
        # you to do here).
        # Warning:
        # External apps should not have relations to any of the objects
        # copied here manually because the draft version will be deleted.
        # If you don't want that to happen, you'll have to be smart about not
        # deleting and recreating all the related objects and instead update
        # them. But it may not always be possible or straight forward.
        pass

    def publisher_update_relations_exclude(self, old_obj):
        return (
            # (<source model>, 'field_name'),
            # (Article.categories.through, 'to_article'),
            # (SomeModel, 'fk_field_to_me'),
        )

    def publisher_can_publish(self):
        # Checks whether the data and all linked data is ready to publish.
        # Raise ValidationError if not.
        pass

    def publisher_user_can_publish(self, user):
        # Checks whether the user has permissions to publish.
        # Return True or False.
        return True
    # /USER OVERRIDABLE
