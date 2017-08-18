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

from .publisher.master import ParlerMasterPublisher
from .publisher.translation import ParlerTranslationPublisher
from .publisher.translation_aware import ParlerPublisher


class ParlerPublisherModelMixin(PublisherModelMixin):
    # USER OVERRIDABLE
    def publisher_copy_relations_for_translation(self, old_obj):
        language_code = self.language_code
        # e.g copy placeholders for a specific language
    # /USER OVERRIDABLE

    @cached_property
    def publisher(self):
        return ParlerPublisher(instance=self, name='publisher')

    # def get_master(self):
    #     # Make sure this is *not* language aware
    #     return self._meta.model.objects.get(pk=self.pk)

    # @property
    # def publisher(self):
    #     if self.language_code:
    #         return self.language_aware_publisher
    #     else:
    #         return self.master_publisher
    #
    @cached_property
    def master_publisher(self):
        return ParlerMasterPublisher(instance=self, name='master_publisher')

    def publisher_draft_or_published_translations_only_prefer_drafts(self):
        return self.publisher.all_translations(prefer_drafts=True)

    def publisher_draft_or_published_translations_only_prefer_published(self):
        return self.publisher.all_translations(prefer_drafts=False)

    class Meta:
        abstract = True


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

        # def get_parler_translation_publisher(translation):
        #     master = translation.master
        #     master.set_current_language(translation.language_code)
        #     return master.publisher

        fields['publisher'] = cached_property(
            lambda self: ParlerTranslationPublisher(
                instance=self,
                name='publisher',
            )
        )
        super(ParlerPublisherTranslatedFields, self).__init__(meta, **fields)

