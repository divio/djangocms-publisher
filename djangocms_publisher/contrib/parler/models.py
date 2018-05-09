# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.utils.functional import cached_property
from parler.models import TranslatedFields

from cms.utils.i18n import get_current_language

from ...models import PublisherModelMixin
from .publisher.master import ParlerMasterPublisher
from .publisher.translation import ParlerTranslationPublisher
from .publisher.translation_aware import ParlerPublisher


class ParlerPublisherModelMixin(PublisherModelMixin):

    class Meta:
        abstract = True

    # USER OVERRIDABLE
    def publisher_copy_relations_for_translation(self, old_obj):
        pass
        # language_code = self.language_code
        # e.g copy placeholders for a specific language
    # /USER OVERRIDABLE

    @cached_property
    def publisher(self):
        return ParlerPublisher(instance=self, name='publisher')

    @cached_property
    def master_publisher(self):
        return ParlerMasterPublisher(instance=self, name='master_publisher')

    def publisher_draft_or_published_translations_only_prefer_drafts(self):
        return self.publisher.all_translations(prefer_drafts=True)

    def publisher_draft_or_published_translations_only_prefer_published(self):
        return self.publisher.all_translations(prefer_drafts=False)

    def get_public_url(self, language=None):
        # Used by django-cms toolbar to get the url for switching to the public
        # version of the object
        if not language:
            language = get_current_language()
        published_version = self.publisher.get_published_version()
        if published_version:
            return published_version.get_absolute_url(language=language)
        return ''

    def get_draft_url(self, language=None):
        # Used by django-cms toolbar to get the url for switching to the draft
        # version of the object. Contains some ugly magic to create the draft
        # if it does not exist yet.
        if not language:
            language = get_current_language()
        draft_version = self.publisher.get_draft_version()
        if draft_version:
            return draft_version.get_absolute_url(language=language)
        return ''


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

        fields['publisher'] = cached_property(
            lambda self: ParlerTranslationPublisher(
                instance=self,
                name='publisher',
            )
        )
        super(ParlerPublisherTranslatedFields, self).__init__(meta, **fields)
