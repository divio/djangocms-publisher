# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from collections import OrderedDict

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
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

    @cached_property
    def admin_urls(self):
        from ..admin import ParlerAdminUrls
        return ParlerAdminUrls(self.instance)

    def get_draft_version(self):
        obj = super(ParlerPublisher, self).get_draft_version()
        if obj:
            try:
                obj.set_current_language(self.instance.language_code)
                return obj
            except ObjectDoesNotExist:
                pass
        return None

    def get_published_version(self):
        obj = super(ParlerPublisher, self).get_published_version()
        if obj:
            try:
                obj.set_current_language(self.instance.language_code)
                return obj
            except ObjectDoesNotExist:
                pass
        return None

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

        draft_translation = self.get_translation()
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
        published_translation = self.get_translation()
        draft_translation = published_translation.publisher.create_draft()
        draft = draft_translation.master
        draft.set_current_language(language_code)
        return draft

    @transaction.atomic
    def discard_draft(self, update_relations=True):
        try:
            translation = self.get_translation()
            translation.discard_draft()
        except ObjectDoesNotExist:
            pass
        if not self.instance.translations.all().exists():
            self.instance.master_publisher.disard_draft()

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
    def publish_deletion(self):
        translation = self.instance.get_translation(self.instance.language_code)
        translation.publish_deletion()
        if not self.instance.translations.all().exists():
            self.instance.delete()

    @transaction.atomic
    def request_deletion(self):
        published = self.get_published_version()
        if self.instance != published:
            return published.publisher.request_deletion()
        language_code = published.language_code
        published_translation = published.get_translation(language_code)
        published_translation.publisher.request_deletion()
        return refresh_from_db(self.instance)

    @transaction.atomic
    def discard_deletion_request(self):
        assert self.is_published_version
        if self.instance.master_publisher.has_pending_deletion_request:
            self.instance.master_publisher.discard_deletion_request()
        translation = self.instance.get_translation(self.instance.language_code)
        translation.publisher.discard_deletion_request()

    def all_translations(self, prefer_drafts=None):
        return self.all_translations_dict(prefer_drafts=prefer_drafts).values()

    def all_translations_dict(self, prefer_drafts=None):
        # FIXME: reduce queries
        draft = self.instance.master_publisher.get_draft_version()
        published = self.instance.master_publisher.get_published_version()
        master_pks = set()
        if draft:
            master_pks.add(draft.pk)
        if published:
            master_pks.add(published.pk)
        print(master_pks)
        qs = self.instance._parler_meta.root_model.objects.filter(master_id__in=master_pks)
        translations = {}
        for translation in qs:
            lang = translations.setdefault(translation.language_code, {})
            if translation.publisher.is_draft_version:
                lang['draft'] = translation
            else:
                lang['published'] = translation
        result = {}
        if prefer_drafts is True:
            for lang, versions in translations.items():
                if 'draft' in versions:
                    result[lang] = versions['draft']
                else:
                    result[lang] = versions['published']
        if prefer_drafts is False:
            for lang, versions in translations.items():
                if 'published' in versions:
                    result[lang] = versions['published']
                else:
                    result[lang] = versions['draft']
        return result

    def translation_states(self, all_translations=None):
        return (
            self.translation_states_dict(all_translations=all_translations)
            .values()
        )

    def translation_states_dict(self, all_translations=None):
        all_language_codes = [code for code, name in settings.LANGUAGES]
        if all_translations is None:
            all_translations = {
                trans.language_code: trans
                for trans in self.all_translations(prefer_drafts=False)
            }
        all_states = OrderedDict()
        for language_code in all_language_codes:
            if language_code in all_translations:
                all_states[language_code] = all_translations[language_code].publisher.state
            else:
                all_states[language_code] = {
                    'identifier': 'empty',
                    'css_class': 'empty',
                    'text': _('Does not exist'),
                    'language_code': language_code,
                }
        return all_states
