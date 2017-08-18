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


class ParlerPublisher(Publisher):
    """
    A publisher object for the language aware parler master object. It combines
    actions from the master publisher and the translation publisher.
    It is similar to the parler master object which has screwed together the
    main object and an active translation.
    """
    def get_draft_version(self):
        obj = super(ParlerPublisher, self).get_draft_version()
        if not obj.language_code:
            obj.set_current_language(self.instance.language_code)
        return obj

    def get_published_version(self):
        obj = super(ParlerPublisher, self).get_published_version()
        if not obj.language_code:
            obj.set_current_language(self.instance.language_code)
        return obj

    @property
    def language_code(self):
        return self.instance.language_code

    def get_translation(self):
        return self.instance.get_translation(self.language_code)

    @property
    def has_published_version(self):
        return self.get_translation().publisher.has_published_version

    @property
    def has_pending_changes(self):
        return self.get_translation().publisher.has_pending_changes

    @property
    def has_pending_deletion_request(self):
        return self.get_translation().publisher.has_pending_deletion_request

    @transaction.atomic
    def publish(self, validate=True, delete=True, update_relations=True, now=None):
        # publish the master object (but don't delete it)
        # publish this translation
        # delete myself (translation)
        # if there are no other draft translations, delete the master draft
        draft = self.get_draft_version()
        if draft != self.instance:
            return self.get_publisher(draft).publish(
                validate=validate,
                delete=delete,
                update_relations=update_relations,
                now=now,
            )

        if validate:
            self.can_publish()
        now = now or timezone.now()
        language_code = self.instance.language_code

        draft_translation = self.instance.get_translation(language_code)
        published_translation = draft_translation.publisher.publish(
            delete=False,
            update_relations=False,
            now=now,
        )

        if delete:
            # Delete the draft translation
            draft_translation.delete()
            # If there are no more translation drafts: delete the master draft too.
            if not draft_translation.master.translations.all().exists():
                # FIXME: update_relations before master is deleted.
                draft_translation.master.delete()
        published = refresh_from_db(published_translation.master)
        published.set_current_language(language_code)
        return published

    @transaction.atomic
    def create_draft(self):
        assert self.is_published_version
        # published_translation = self.instance
        if self.has_pending_deletion_request:
            self.discard_deletion_request()
        language_code = self.instance.language_code
        published_translation = self.instance.get_translation(language_code)
        draft_translation = published_translation.publisher.create_draft()
        return draft_translation

    def copy_relations(self, old_obj):
        # Call a method on the master object so any app specific relations can
        # be copied (e.g Placeholders or relations on the translated obj)
        new_obj = self.instance
        language_code = new_obj.language_code

        new_obj.master_publisher.copy_relations(old_obj=old_obj)
        new_obj.get_translation(language_code).publisher.copy_relations(old_obj=old_obj)

    def can_publish(self):
        self.instance.publisher_can_publish()

    @transaction.atomic
    def request_deletion(self):
        published = self.get_published_version()
        if self.instance != published:
            return published.publisher.request_deletion()
        language_code = published.language_code
        published_translation = published.get_translation(language_code)
        published_translation.publisher_translation_deletion_requested = True
        published_translation.save(update_fields=['publisher_translation_deletion_requested'])

        # FIXME: delete the draft version
        # FIXME: caveat: can't delete the last translation. be smart.
        # draft = self.get_draft_version()
        # if draft:
        #     draft_translation.delete()
        return refresh_from_db(self.instance)

    @transaction.atomic
    def discard_requested_deletion(self):
        assert self.is_published_version
        self.instance.publisher_translation_deletion_requested = False
        self.instance.save(
            update_fields=['publisher_translation_deletion_requested']
        )
