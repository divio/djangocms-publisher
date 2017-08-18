# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from djangocms_publisher.contrib.parler.admin import PublisherParlerAdminMixin
from parler.admin import TranslatableAdmin
from . import models


class ParlerThingAdmin(PublisherParlerAdminMixin, TranslatableAdmin):
    list_display = (
        'name',
        'publisher_status',
        'publisher_translation_states',
        'a_boolean',
        'publisher_is_published_version',
    )
    search_fields = (
        'translations__name',
        'attachments__name',
    )
    readonly_fields = (
        'publisher_status',
        'publisher_translation_states',
        'publisher_state_debug',
    )
    fieldsets = [
        (None, {
            'fields': (
                'publisher_status',
                'name',
                'a_boolean',
            ),
        }),
        ('Debug', {
            'fields': (
                'publisher_state_debug',
            )
        })
    ]

    def get_changelist(self, request, **kwargs):
        # FIXME: create a helper in djangocms-publisher to make this easier
        # We override get_queryset on the ChangeList here because we want to
        # only show draft or published on the change list. But still allow
        # looking at either on the change_view.
        ChangeList = super(ParlerThingAdmin, self).get_changelist(request, **kwargs)

        class DraftOrLiveOnlyChangeList(ChangeList):
            def get_queryset(self, request):
                return (
                    super(DraftOrLiveOnlyChangeList, self)
                    .get_queryset(request)
                    .publisher_draft_or_published_only_prefer_published()
                )
        return DraftOrLiveOnlyChangeList


class ExternalThingAdmin(admin.ModelAdmin):
    pass


admin.site.register(models.ParlerThing, ParlerThingAdmin)
