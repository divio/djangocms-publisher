# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from .utils.copying import (
    DEFAULT_COPY_EXCLUDE_FIELDS,
    copy_object,
    refresh_from_db)
from .utils import relations


PUBLISHER_STATE_CHOICES = (
    ('published', 'Published'),
    ('not_published', 'Not published'),
    ('pending_changes', 'Published, pending changes'),
    ('pending_deletion', 'Published, pending deletion'),
    # nocontent is for a case where there is no content at all, neither
    # draft nor published. Only relevant for translations of a main object.
    ('empty', 'No Content'),
)


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


class Publisher(object):
    """
    Discriptor for use on objects that should get draft/published funtionality.

    """
    def __init__(self, instance):
        self.instance = instance

    @property
    def is_published_version(self):
        return self.instance.publisher_is_published_version

    @is_published_version.setter
    def is_published_version(self, value):
        self.instance.publisher_is_published_version = bool(value)

    @property
    def is_draft_version(self):
        return not self.instance.publisher_is_published_version

    @is_draft_version.setter
    def is_draft_version(self, value):
        self.instance.publisher_is_published_version = not bool(value)

    @property
    def published_at(self):
        return self.instance.publisher_published_at

    @published_at.setter
    def published_at(self, value):
        self.instance.publisher_published_at = value

    @property
    def has_pending_changes(self):
        if self.is_draft_version:
            return True
        try:
            # Query! :-(
            # Can be avoided by using
            # .select_related('draft') in the queryset.
            return bool(self.instance.publisher_draft_version)
        except ObjectDoesNotExist:
            return False

    @property
    def has_pending_deletion_request(self):
        return self.instance.publisher_deletion_requested

    @property
    def has_published_version(self):
        if self.is_published_version:
            return True
        # Query! :-(
        return bool(self.get_published_version())

    def get_draft_version(self):
        if self.is_draft_version:
            return self.instance
        elif self.has_pending_changes:
            # DB Query
            return self.instance.publisher_draft_version
        return None

    def get_published_version(self):
        if self.is_published_version:
            return self.instance
        elif self.instance.publisher_published_version_id:
            # DB Query
            return self.instance.publisher_published_version
        return None

    @transaction.atomic
    def publish(self, validate=True, delete=True, update_relations=True):
        draft = self.get_draft_version()
        published = self.get_published_version()
        assert draft
        if validate:
            draft.publisher_can_publish()
        now = timezone.now()

        # * update the live version with the data from the draft
        if not published:
            # There is no published version yet. Create one.
            published = draft._meta.model()
            published_created = True
        else:
            published_created = False
        published.publisher_is_published_version = True
        published.publisher_published_at = now
        published.publisher.copy_object(old_obj=draft)  # saves
        if update_relations:
            # * find any other objects still pointing to the draft version and
            #   switch them to the live version. (otherwise cascade or set null
            #   would yield unexpected results)
            relations.update_relations(
                old_obj=draft,
                new_obj=published,
                exclude=relations.ignore_stuff_to_dict(
                    draft.publisher.update_relations_exclude(old_obj=draft)
                )
            )
        if delete:
            # * Delete draft (self)
            draft.delete()
        elif published_created:
            draft.publisher_published_version = published
            draft.save()
        # Refresh from db to get the latest version without any cached stuff.
        # refresh_from_db() does not work in some cases because parler
        # caches translations at _translations_cache which may remain with stale
        # data.
        published = self.instance._meta.model.objects.get(pk=published.pk)
        return published

    def get_or_create_draft(self):
        draft = self.get_draft_version()
        if draft:
            return draft, False
        return self.create_draft(), True

    @transaction.atomic
    def create_draft(self):
        if self.has_pending_deletion_request:
            self.discard_deletion_request()
        draft = self.instance._meta.model.objects.get(pk=self.instance.pk)
        draft.pk = draft.id = None
        draft.publisher_is_published_version = False
        draft.publisher_published_version = self.instance
        draft.save()
        draft.publisher.copy_relations(old_obj=self.instance)
        return refresh_from_db(draft)

    def discard_draft(self, update_relations=True):
        draft = self.get_draft_version()
        if not draft:
            return
        published = self.get_published_version()
        if not published:
            self.instance.delete()
            return
        if update_relations:
            relations.update_relations(
                old_obj=draft,
                new_obj=published,
                exclude=relations.ignore_stuff_to_dict(
                    self.update_relations_exclude(old_obj=draft),
                )
            )
        draft.delete()

    def request_deletion(self):
        draft = self.get_draft_version()
        published = self.get_published_version()
        published.publisher_deletion_requested = True
        published.save(update_fields=['publisher_deletion_requested'])
        if draft:
            draft.discard_draft()
        return published

    def discard_deletion_request(self):
        published = self.get_published_version()
        published.publisher_deletion_requested = False
        published.save(update_fields=['publisher_deletion_requested'])

    def publish_deletion(self):
        assert self.has_pending_deletion_request
        self.instance.delete()
        self.instance.id = self.instance.pk = None
        return self.instance

    def copy_object(self, old_obj, commit=True):
        new_obj = self.instance
        copy_object(
            new_obj=new_obj,
            old_obj=old_obj,
            exclude_fields=self.copy_object_exclude_fields(),
        )
        if commit:
            new_obj.save()
            new_obj.publisher.copy_relations(old_obj=old_obj)

    def copy_relations(self, old_obj):
        self.instance.publisher_copy_relations(old_obj=old_obj)

    def copy_object_exclude_fields(self):
        return (
            set(DEFAULT_COPY_EXCLUDE_FIELDS) |
            set(self.instance.publisher_copy_object_exclude_fields)
        )

    def update_relations_exclude(self, old_obj):
        return self.instance.publisher_update_relations_exclude(old_obj=old_obj)

    def can_publish(self):
        draft = self.get_draft_version()
        if draft:
            draft.publisher_can_publish()

    def user_can_publish(self, user):
        draft = self.get_draft_version()
        if draft:
            return draft.publisher_user_can_publish(user=user)
        else:
            return False

    def available_actions(self, user):
        actions = {}
        if self.has_pending_deletion_request:
            actions['discard_requested_deletion'] = {}
            actions['publish_deletion'] = {}
        if (
            self.is_draft_version and
            self.has_pending_changes
        ):
            actions['publish'] = {}
        if (
            self.is_draft_version and
            self.has_pending_changes and
            self.has_published_version
        ):
            actions['discard_draft'] = {}
        if self.is_published_version and not self.has_pending_changes:
            actions['create_draft'] = {}
        if self.is_published_version and not self.has_pending_deletion_request:
            actions['request_deletion'] = {}
        for action_name, data in actions.items():
            data['name'] = action_name
            if action_name in ('publish', 'publish_deletion'):
                # FIXME: do actual permission check
                data['has_permission'] = user.is_superuser
            else:
                data['has_permission'] = True
        return actions

    def allowed_actions(self, user):
        return [
            action
            for action, data in self.available_actions(user).items()
            if data['has_permission']
        ]

    @property
    def status_text(self):
        if self.has_pending_deletion_request:
            return _('Pending deletion')
        elif self.is_draft_version:
            if self.has_published_version:
                return _('Unpublished changes')
            else:
                return _('Not published')
        return ''

    def add_status_label(self, label):
        """
        Extra label to be added to the default string representation of objects
        to identify their status.
        """
        status = self.status_text
        if status:
            return '{} [{}]'.format(label, status.upper())
        return '{}'.format(label)

    @property
    def state(self):
        choices = dict(PUBLISHER_STATE_CHOICES)
        state_dict = {
            'is_published': self.has_published_version,
            'has_pending_changes': self.has_pending_changes,
            'has_pending_deletion_request': self.has_pending_deletion_request,
        }
        if self.has_pending_deletion_request:
            state_id = 'pending_deletion'
            css_class = 'pending_deletion'
        elif self.has_published_version and self.has_pending_changes:
            state_id = 'pending_changes'
            css_class = 'dirty'
        elif self.has_published_version and not self.has_pending_changes:
            state_id = 'published'
            css_class = 'published'
        elif not self.has_published_version and self.has_pending_changes:
            state_id = 'not_published'
            css_class = 'unpublished'
        else:
            state_id = 'empty'
            css_class = 'empty'
        state_dict['identifier'] = state_id
        state_dict['css_class'] = css_class
        state_dict['text'] = choices[state_id]
        return state_dict


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
        return Publisher(instance=self)

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
