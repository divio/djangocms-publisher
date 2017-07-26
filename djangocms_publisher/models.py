# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from .dependency_graph import update_relations


class PublisherQuerySetMixin(object):
    def publisher_published(self):
        return self.filter(publisher_is_published=True)

    def publisher_drafts(self):
        return self.filter(publisher_is_published=False)

    def publisher_pending_deletion(self):
        return self.filter(
            publisher_is_published=True,
            publisher_deletion_requested=True,
        )

    def publisher_pending_changes(self):
        return self.filter(
            Q(publisher_is_published=False) |
            Q(publisher_is_published=True, publisher_draft__isnull=False)
        )

    def publisher_drafts_or_published_only(self):
        """
        Returns a queryset that does not return duplicates of the same object
        if there is both a draft and published version.
        only a draft: include the draft
        only a published: include the published
        draft and published: inlcude the published

        So shorter version: exclude drafts that have a published version.
        """
        return self.filter(
            # published objects
            Q(publisher_is_published=True) |
            # OR drafts without a published version
            Q(publisher_is_published=False, publisher_published__isnull=True)
        )


class PublisherQuerySet(PublisherQuerySetMixin, models.QuerySet):
    pass


class PublisherLogicMixin(object):
    _publisher_ignore_copy_fields = (
        'pk',
        'id',
        'publisher_is_published',
        'publisher_published',
        'publisher_draft',
        'publisher_published_at',
        'publisher_deletion_requested',
    )
    publisher_ignore_copy_fields = ()

    def publisher_get_ignore_copy_fields(self):
        return (
            set(self._publisher_ignore_copy_fields) |
            set(self.publisher_ignore_copy_fields)
        )

    # USER OVERRIDABLE METHODS
    def publisher_copy_relations(self, old_obj):
        pass

    def publisher_copy_object(self, old_obj, commit=True):
        # TODO: use the id swapping trick (but remember to set live_id too!)
        for field in self._meta.get_fields():
            if (
                not field.concrete or
                field.name in self.publisher_get_ignore_copy_fields()
            ):
                continue
            setattr(self, field.name, getattr(old_obj, field.name))
        if commit:
            self.save()
            self.publisher_copy_relations(old_obj=old_obj)

    def publisher_can_publish(self):
        assert self.publisher_is_draft_version
        # FOR SUBCLASSES
        # Checks whether the data and all linked data is ready to publish.
        # Raise ValidationError if not.

    def publisher_user_can_publish(self, user):
        # FOR SUBCLASSES
        # Checks whether the user has permissions to publish
        return True
    # END USER OVERRIDABLE METHODS
    #
    # def clean(self):
    #     super(PublisherLogicMixin, self).clean()
    #     if self.publisher_is_published_version and self.publisher_published_version_id:
    #         raise ValidationError(
    #             'A live object can\'t set the published relationship.'
    #         )
    #     if self.publisher_is_draft_version and self.publisher_deletion_requested:
    #         raise ValidationError('invalid')

    @property
    def publisher_is_draft(self):
        return not self.publisher_is_published_version

    @property
    def publisher_has_published_version(self):
        if self.publisher_is_published_version:
            return True
        else:
            return bool(self.publisher_published_version_id)

    @cached_property
    def publisher_has_pending_changes(self):
        if self.publisher_is_draft_version:
            return True
        else:
            try:
                # Query! Can probably be avoided by using
                # .select_related('draft') in the queryset.
                return bool(self.publisher_draft_version)
            except ObjectDoesNotExist:
                return False

    @property
    def publisher_has_pending_deletion_request(self):
        return self.publisher_is_published_version and self.publisher_deletion_requested

    @transaction.atomic
    def create_draft(self):
        assert self.publisher_is_published_version
        if self.publisher_has_pending_deletion_request:
            self.publisher_discard_requested_deletion()
        # TODO: Get draft without a query (copy in memory)
        # FIXME: use the same logic as publishing.
        draft = self._meta.model.objects.get(id=self.id)
        draft.pk = None
        draft.id = None
        draft.is_published = False
        draft.published = self
        # If save() was called even though a draft already exists,
        # we'll get the db error here.
        draft.save()
        draft.copy_relations(old_obj=self)
        return draft

    @transaction.atomic
    def publisher_discard_draft(self):
        assert self.publisher_is_draft_version
        update_relations(obj=self, new_obj=self.publisher_published_version)
        self.delete()

    @transaction.atomic
    def publisher_publish(self, validate=True):
        assert self.publisher_is_draft_version
        draft = self
        if validate:
            draft.publisher_can_publish()
        now = timezone.now()
        existing_published = draft.publisher_published_version
        if not existing_published:
            # This means there is no existing published version. So we can just
            # make this draft the published version.
            # As a nice side-effect all existing ForeignKeys pointing to this
            # object will now be automatically pointing the published version.
            # Win-win.
            draft.publisher_is_live = True
            draft.publisher_published_at = now
            draft.save()
            return draft

        # There is an existing live version:
        # * update the live version with the data from the draft
        published = draft.publisher_published_version
        published.publisher_published_at = now
        published.publisher_copy_object(old_obj=self)
        # * find any other objects still pointing to the draft version and
        #   switch them to the live version. (otherwise cascade or set null
        #   would yield unexpected results)
        update_relations(obj=draft, new_obj=published)
        # * Delete draft (self)
        draft.delete()
        return published

    @transaction.atomic
    def publisher_request_deletion(self):
        assert (
            self.publisher_is_draft_version and self.publisher_has_published_version or
            self.publisher_is_published_version
        )
        # shortcut to be able to request_deletion on a draft. Preferrably this
        # should be done on the live object.
        if self.publisher_is_draft_version:
            return self.publisher_published_version.request_deletion()

        # It is a published object
        published = self
        if self.publisher_has_pending_changes:
            draft = published.publisher_draft_version
        else:
            draft = None

        published.publisher_deletion_requested = True
        published.save(update_fields=['publisher_deletion_requested'])
        if draft:
            draft.delete()
        return published

    @transaction.atomic
    def publisher_discard_requested_deletion(self):
        assert self.publisher_is_published_version
        self.publisher_deletion_requested = False
        self.save(update_fields=['publisher_deletion_requested'])

    @transaction.atomic
    def publisher_publish_deletion(self):
        assert self.publisher_has_pending_deletion_request
        self.delete()
        self.id = None
        return self

    def publisher_get_live(self):
        if self.publisher_is_published_version:
            return self
        if self.publisher_published_version_id:
            return self.publisher_published_version
        return None

    def publisher_available_actions(self, user):
        actions = {}
        if self.publisher_deletion_requested:
            actions['discard_requested_deletion'] = {}
            actions['publish_deletion'] = {}
        if self.publisher_is_draft_version and self.publisher_has_pending_changes:
            actions['publish'] = {}
        if (
            self.publisher_is_draft_version and
            self.publisher_has_pending_changes and
            self.publisher_has_published_version
        ):
            actions['discard_draft'] = {}
        if self.publisher_is_published_version and not self.publisher_has_pending_changes:
            actions['create_draft'] = {}
        if self.publisher_is_published_version and not self.publisher_deletion_requested:
            actions['request_deletion'] = {}
        for action_name, data in actions.items():
            data['name'] = action_name
            if action_name in ('publish', 'publish_deletion'):
                # FIXME: do actual permission check
                data['has_permission'] = user.is_superuser
            else:
                data['has_permission'] = True
        return actions

    def publisher_allowed_actions(self, user):
        return [
            action
            for action, data in self.publisher_available_actions(user).items()
            if data['has_permission']
        ]

    @property
    def publisher_status_text(self):
        if self.publisher_has_pending_deletion_request:
            return _('Pending deletion')
        elif self.publisher_is_draft_version:
            if self.publisher_has_published_version:
                return _('Unpublished changes')
            else:
                return _('Not published')
        return ''

    def publisher_add_status_label(self, label):
        """
        Extra label to be added to the default string representation of objects
        to identify their status.
        """
        status = self.publisher_status_text
        if status:
            return '{} [{}]'.format(label, status.upper())
        else:
            return '{}'.format(label)


class PublisherModelMixin(models.Model):
    publisher_is_published_version = models.BooleanField(
        default=False,
        editable=False,
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
    )

    objects = PublisherQuerySet.as_manager()

    class Meta:
        abstract = True


class PublisherMixin(PublisherLogicMixin, PublisherModelMixin):
    class Meta:
        abstract = True
