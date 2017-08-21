# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import models, transaction
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from ....utils.copying import (
    get_fields_to_copy,
    refresh_from_db)
from ....models import PUBLISHER_STATE_CHOICES, PublisherModelMixin, Publisher


class ParlerTranslationPublisher(Publisher):
    """
    A publisher object for the parler translation model object.
    """

    @property
    def is_published_version(self):
        return self.instance.master.master_publisher.is_published_version

    @property
    def is_draft_version(self):
        return not self.is_published_version

    @property
    def has_published_version(self):
        if self.is_published_version:
            return True
        return bool(self.get_published_version())

    @property
    def has_pending_changes(self):
        return bool(self.get_draft_version())

    @property
    def has_pending_deletion_request(self):
        published_translation = self.get_published_version()
        if (
            published_translation and
            published_translation.publisher_translation_deletion_requested
        ):
            return True
        return False

    def get_draft_version(self):
        if self.is_draft_version:
            return self.instance
        draft_master = self.instance.master.master_publisher.get_draft_version()
        if not draft_master:
            return None
        return (
            draft_master
            .translations
            .filter(language_code=self.instance.language_code)
            .first()
        )

    def get_published_version(self):
        if self.is_published_version:
            return self.instance
        if not self.instance.master.publisher_published_version_id:
            return None
        # FIXME: make more efficient. Use parler caches?
        return (
            self
            .instance
            .master
            .publisher_published_version
            .translations
            .filter(language_code=self.instance.language_code)
            .first()
        )

    def publish(self, validate=True, delete=True, update_relations=True, now=None):
        now = now or timezone.now()
        draft_translation = self.get_draft_version()
        if draft_translation != self.instance:
            return draft_translation.publisher.publish()
        draft_master = self.instance.master

        # Ensure we have a published master for this translation
        published_master = draft_master.master_publisher.publish(
            delete=False,
            update_relations=False,
        )
        # Publish the translation
        fields_to_copy = get_fields_to_copy(
            draft_translation,
            exclude_fields={'master', 'language_code'},
        )
        fields_to_copy['publisher_translation_published_at'] = now
        published_translation, translation_created = (
            published_master
            .translations
            .update_or_create(
                language_code=draft_translation.language_code,
                defaults=fields_to_copy,
            )
        )

        published_translation.publisher.copy_relations(
            old_obj=draft_translation,
        )
        if delete:
            # Delete the draft translation
            draft_translation.delete()
        return published_translation

    @transaction.atomic
    def create_draft(self):
        assert self.is_published_version
        if self.has_pending_deletion_request:
            self.discard_deletion_request()
        published_master = self.instance.master
        published_translation = self.instance
        draft_master, draft_master_created = published_master.master_publisher.get_or_create_draft()
        fields_to_copy = get_fields_to_copy(
            published_translation,
            exclude_fields={'master', 'language_code'},
        )
        draft_translation, draft_translation_created = (
            draft_master
            .translations
            .update_or_create(
                language_code=published_translation.language_code,
                defaults=fields_to_copy,
            )
        )
        draft_translation.publisher.copy_relations(
            old_obj=published_translation,
        )
        return draft_translation

    def copy_relations(self, old_obj):
        language_code = old_obj.language_code
        new_master_obj = self.instance.master
        new_master_obj.set_current_language(language_code)
        old_master_obj = old_obj.master
        old_master_obj.set_current_language(language_code)
        new_master_obj.publisher_copy_relations_for_translation(old_obj=old_master_obj)

    def get_or_create_draft(self):
        draft = self.get_draft_version()
        if draft:
            return draft, False
        return self.create_draft(), True

    @transaction.atomic
    def publish_deletion(self):
        assert self.instance.publisher_translation_deletion_requested
        self.instance.delete()

    @transaction.atomic
    def request_deletion(self):
        published = self.get_published_version()
        if self.instance != published:
            return published.publisher.request_deletion()
        published.publisher_translation_deletion_requested = True
        published.save(
            update_fields=['publisher_translation_deletion_requested'],
        )
        draft = published.publisher.get_draft_version()
        if draft:
            draft.publisher.discard_draft()

    def update_relations_exclude(self, old_obj):
        return ()

    @transaction.atomic
    def discard_deletion_request(self):
        self.instance.publisher_translation_deletion_requested = False
        self.instance.save(
            update_fields=['publisher_translation_deletion_requested'],
        )

    @property
    def state(self):
        choices = dict(PUBLISHER_STATE_CHOICES)
        published = self.get_published_version()
        draft = self.get_draft_version()
        is_published = bool(published)
        has_pending_changes = bool(draft)
        has_pending_deletion_request = published and published.publisher.has_pending_deletion_request
        if published:
            language_code = published.language_code
        else:
            language_code = draft.language_code
        state_dict = {
            'is_published': is_published,
            'has_pending_changes': has_pending_changes,
            'has_pending_deletion_request': has_pending_deletion_request,
            'language_code': language_code,
        }
        if has_pending_deletion_request:
            state_id = 'pending_deletion'
            css_class = 'pending_deletion'
        elif is_published and has_pending_changes:
            state_id = 'pending_changes'
            css_class = 'dirty'
        elif is_published and not has_pending_changes:
            state_id = 'published'
            css_class = 'published'
        elif not is_published and has_pending_changes:
            state_id = 'not_published'
            css_class = 'unpublished'
        else:
            state_id = 'empty'
            css_class = 'empty'
        state_dict['identifier'] = state_id
        state_dict['css_class'] = css_class
        state_dict['text'] = choices[state_id]
        return state_dict

    def available_actions(self, user):
        actions = {}
        if self.has_pending_deletion_request:
            actions['discard_requested_deletion'] = {}
            actions['publish_deletion'] = {}
        if self.is_draft_version and self.has_pending_changes:
            actions['publish'] = {}
        if (
            self.is_draft_version and
            self.has_pending_changes and
            self.has_published_version
        ):
            actions['discard_draft'] = {}
        if self.is_published_version and not self.has_pending_changes:
            actions['create_draft'] = {}
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
