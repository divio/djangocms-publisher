# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from collections import OrderedDict

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from ...utils.copying import (
    get_fields_to_copy,
    refresh_from_db)
from ...models import PUBLISHER_STATE_CHOICES, PublisherModelMixin, Publisher


class ParlerMasterPublisher(Publisher):
    """
    A publisher object for the parler master object. This is not directly
    accessible and only exists to be used by the language specific parler
    publisher.
    """
    pass


class ParlerPublisher(Publisher):
    """
    A publisher object for the language aware parler master object.
    """
    @cached_property
    def master_publisher(self):
        # FIXME: do we need to do something with self.instance here to get a
        #        real non-language-aware instance?
        return ParlerMasterPublisher(self.instance)




# class ParlerTranslationPublisher(Publisher):
#     """
#     A publisher object for the parler translation model object.
#     """
#     @cached_property
#     def _language_aware_master(self):
#         master = self.instance.master
#         master.set_current_language(self.instance.language_code)
#         return master
#
#     @property
#     def has_pending_changes(self):
#         return self._language_aware_master.publisher.has_pending_changes
#
#     @property
#     def is_published_version(self):
#         return self._language_aware_master.publisher.is_published_version
#
#     @property
#     def is_draft_version(self):
#         return self._language_aware_master.publisher.is_draft_version


class ParlerPublisherModelMixin(PublisherModelMixin):

    @cached_property
    def publisher(self):
        # FIXME: assert that this is a language aware obj
        return ParlerPublisher(self)

    def publisher_all_translations(self, prefer_drafts=None):
        # FIXME: reduce queries
        draft = self.publisher_get_draft_version()
        published = self.publisher_get_published_version()
        master_pks = set()
        if draft:
            master_pks.add(draft.pk)
        if published:
            master_pks.add(published.pk)
        qs = self._parler_meta.root_model.objects.filter(master_id__in=master_pks)
        translations = {}
        for translation in qs:
            lang = translations.setdefault(translation.language_code, {})
            if translation.translation_publisher.is_draft_version:
                lang['draft'] = translation
            else:
                lang['published'] = translation
        result = []
        if prefer_drafts is True:
            for lang, versions in translations.items():
                if 'draft' in versions:
                    result.append(versions['draft'])
                else:
                    result.append(versions['published'])
        if prefer_drafts is False:
            for lang, versions in translations.items():
                if 'published' in versions:
                    result.append(versions['published'])
                else:
                    result.append(versions['draft'])
        return result

    def publisher_translations_state(self):
        all_language_codes = [itm[0] for itm in settings.LANGUAGES]
        all_translations = {
            trans.language_code: trans
            for trans in self.publisher_all_translations(prefer_drafts=False)
        }
        all_states = OrderedDict()
        for language_code in all_language_codes:
            if language_code in all_translations:
                all_states[language_code] = all_translations[language_code].translation_publisher.state
            else:
                all_states[language_code] = {
                    'identifier': 'empty',
                    'css_class': 'empty',
                    'text': _('Does not exist'),
                    'language_code': language_code,
                }
        return all_states.values()

    def publisher_draft_or_published_translations_only_prefer_drafts(self):
        return self.publisher_all_translations(prefer_drafts=True)

    def publisher_draft_or_published_translations_only_prefer_published(self):
        return self.publisher_all_translations(prefer_drafts=False)

    def publisher_copy_relations_for_translation(self, old_obj, language_code):
        # old_obj is the old master obj. At this point self (new_obj) and
        # old_obj both have a translation object for the language_code in
        # question
        pass

    class Meta:
        abstract = True


class OldParlerPublisher(object):
    def __init__(self, instance):
        self.instance = instance

    def can_publish(self):
        # FIXME: check the model for a method to call for validation.
        pass

    @transaction.atomic
    def publish(self, validate=True):
        # publish the master object (but don't delete it)
        # publish this translation
        # delete myself (translation)
        # if there are no other draft translations, delete the master draft
        assert self.is_draft_version
        if validate:
            self.can_publish()
        now = timezone.now()

        draft_master = self.instance.master
        draft_translation = self.instance

        # Ensure we have a published master for this translation
        published_master = draft_master.publisher_publish(
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

        published_translation.translation_publisher.copy_relations(
            old_obj=draft_translation,
        )

        # Delete the draft translation
        draft_translation.delete()
        # If there are no more translation drafts: delete the master draft too.
        if not draft_translation.master.translations.all().exists():
            draft_translation.master.delete()
        return published_translation

    @transaction.atomic
    def create_draft(self):
        assert self.is_published_version
        published_translation = self.instance
        if self.has_pending_deletion_request:
            self.discard_requested_deletion()
        draft_master, created_draft_master = self.get_or_create_draft_master()
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
        draft_translation.translation_publisher.copy_relations(
            old_obj=published_translation,
        )
        return draft_translation

    def copy_relations(self, old_obj):
        import ipdb; ipdb.set_trace()
        # Call a method on the master object so any app specific releations can
        # be copied (e.g Placeholders or relations on the translated obj)
        new_translation = self.instance
        old_translation = old_obj
        new_translation.master.publisher_copy_relations_for_translation(
            old_obj=old_translation.master,
            language_code=new_translation.language_code,
        )

    def get_or_create_draft_master(self):
        assert self.is_published_version
        return self.instance.master.publisher_get_or_create_draft()

    @transaction.atomic
    def request_deletion(self):
        assert (
            self.is_draft_version and self.has_published_version or
            self.is_published_version
        )
        # shortcut to be able to request_deletion on a draft. Preferably this
        # should be done on the live object.
        if self.is_draft_version:
            print('Redirecting request_deletion to published version')
            return self.get_published_version().translation_publisher.request_deletion()

        draft_translation = self.get_draft_version()

        self.instance.publisher_translation_deletion_requested = True
        self.instance.save(update_fields=['publisher_translation_deletion_requested'])
        if draft_translation:
            draft_translation.delete()
        return refresh_from_db(self.instance)

    @transaction.atomic
    def discard_requested_deletion(self):
        assert self.is_published_version
        self.instance.publisher_translation_deletion_requested = False
        self.instance.save(
            update_fields=['publisher_translation_deletion_requested']
        )

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

    def publish_deletion(self):
        # FIXME: implement deletion publication
        pass

    @property
    def is_published_version(self):
        return self.instance.master.publisher_is_published_version

    @property
    def is_draft_version(self):
        return self.instance.master.publisher_is_draft_version

    @property
    def has_published_version(self):
        if self.is_published_version:
            return True
        return bool(self.get_published_version())

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

    def get_draft_version(self):
        # FIXME: make more efficient. Use parler caches?
        if self.is_draft_version:
            return self.instance
        published_master = self.instance.master.publisher_get_draft_version()
        if not published_master:
            return None
        return (
            published_master
            .translations
            .filter(language_code=self.instance.language_code)
            .first()
        )

    @property
    def state(self):
        choices = dict(PUBLISHER_STATE_CHOICES)
        published = self.get_published_version()
        draft = self.get_draft_version()
        is_published = bool(published)
        has_pending_changes = bool(draft)
        has_pending_deletion_request = published and published.translation_publisher.has_pending_deletion_request
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

from parler.models import TranslatedFields


class ParlerPublisherTranslatedFields(TranslatedFields):
    def __init__(self, meta=None, **fields):
        fields['publisher_translation_published_at'] = models.DateTimeField(
            blank=True,
            null=True,
            default=None,
            editable=False,
        )
        fields['publisher_translation_deletion_requested'] = models.BooleanField(
            default=False,
            editable=False,
            db_index=True,
        )

        def get_parler_translation_publisher(translation):
            master = translation.master
            master.set_current_language(translation.language_code)
            return master.publisher

        fields['publisher'] = cached_property(
            lambda self: get_parler_translation_publisher(self)
        )
        super(ParlerPublisherTranslatedFields, self).__init__(meta, **fields)

