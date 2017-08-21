# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
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


class Publisher(object):
    """
    Discriptor for use on objects that should get draft/published funtionality.

    """
    def __init__(self, instance, name):
        self.instance = instance
        self.name = name

    def get_publisher(self, obj):
        """
        Returns the publisher instance for the given object with the same name
        is this current instance.
        It is important to use this to get the publisher of a other object of
        the same type to stay within the same publisher for cases where there
        are multiple. Namely with the django-parler publishers when calling
        things on the master_publisher all operations called from the
        master_publisher should stay within the master_publisher.
        :param obj:
        :return:
        """
        return getattr(obj, self.name)

    @cached_property
    def admin_urls(self):
        from .admin import AdminUrls
        return AdminUrls(self.instance)

    @property
    def is_published_version(self):
        return self.instance.publisher_is_published_version

    @property
    def is_draft_version(self):
        return not self.instance.publisher_is_published_version

    @property
    def published_at(self):
        return self.instance.publisher_published_at

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
        published = self.get_published_version()
        if not published:
            return False
        if self.instance != published:
            return self.get_publisher(published).has_pending_deletion_request
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

    def update_relations(self, old_obj):
        new_obj = self.instance
        relations.update_relations(
            old_obj=old_obj,
            new_obj=new_obj,
            exclude=relations.ignore_stuff_to_dict(
                self.update_relations_exclude(old_obj=old_obj)
            )
        )

    @transaction.atomic
    def publish(self, validate=True, delete=True, update_relations=True, now=None):
        draft = self.get_draft_version()
        if draft != self.instance:
            return self.get_publisher(draft).publish(validate=validate, delete=delete, update_relations=update_relations)
        assert self.is_draft_version
        published = self.get_published_version()
        if validate:
            draft.publisher_can_publish()
        now = now or timezone.now()

        # * update the live version with the data from the draft
        if not published:
            # There is no published version yet. Create one.
            published = draft._meta.model()
            published_created = True
        else:
            published_created = False
        published.publisher_is_published_version = True
        published.publisher_published_at = now
        published_publisher = self.get_publisher(published)
        published_publisher.copy_object(old_obj=draft)  # saves
        if update_relations:
            # * find any other objects still pointing to the draft version and
            #   switch them to the live version. (otherwise cascade or set null
            #   would yield unexpected results)
            published_publisher.update_relations(old_obj=draft)
            relations.update_relations(
                old_obj=draft,
                new_obj=published,
                exclude=relations.ignore_stuff_to_dict(
                    self.get_publisher(draft).update_relations_exclude(old_obj=draft)
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
        self.get_publisher(draft).copy_relations(old_obj=self.instance)
        return refresh_from_db(draft)

    @transaction.atomic
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

    @transaction.atomic
    def request_deletion(self):
        draft = self.get_draft_version()
        published = self.get_published_version()
        published.publisher_deletion_requested = True
        published.save(update_fields=['publisher_deletion_requested'])
        if draft:
            self.get_publisher(draft).discard_draft()
        return published

    @transaction.atomic
    def discard_deletion_request(self):
        published = self.get_published_version()
        published.publisher_deletion_requested = False
        published.save(update_fields=['publisher_deletion_requested'])

    @transaction.atomic
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
            self.get_publisher(new_obj).copy_relations(old_obj=old_obj)

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
        if (
            self.is_draft_version and
            not self.has_pending_deletion_request and
            self.has_published_version
        ):
            actions['request_deletion'] = {}
        for action_name, data in actions.items():
            data['name'] = action_name
            if action_name in ('publish', 'publish_deletion'):
                data['has_permission'] = self.user_can_publish(user)
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
