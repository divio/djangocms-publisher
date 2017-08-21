# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import json

from cms.constants import REFRESH_PAGE
from cms.toolbar.items import Dropdown, DropdownToggleButton, ModalButton, \
    Button, BaseButton

from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.utils.translation import (
    ugettext as _, get_language_from_request, override)

from cms.toolbar_base import CMSToolbar
from djangocms_publisher.admin import AdminUrls


class AjaxButton(BaseButton):
    template = 'djangocms_publisher/toolbar/ajax_button.html'

    def __init__(self, name, url, data, icon, active=False, disabled=False):
        self.name = name
        self.url = url
        self.active = active
        self.disabled = disabled
        self.data = data
        self.on_success = REFRESH_PAGE
        self.icon = icon

    def get_context(self):
        return {
            'name': self.name,
            'icon': self.icon,
            'active': self.active,
            'disabled': self.disabled,
            'data': json.dumps(self.data),
            'url': self.url,
            'on_success': self.on_success
        }


def onsite_url(url):
    if '?' in url:
        splitter = '&'
    else:
        splitter = '?'
    return '{}{}redirect=onsite'.format(url, splitter)


class PublisherToolbar(CMSToolbar):
    # TODO: Validate that toolbar is setup correctly (watch_models and supported_apps, ...)
    # watch_models = [Article, ]
    # supported_apps = ('aldryn_newsblog',)

    def setup_publisher_toolbar(self, obj):
        draft_version = obj.publisher.get_draft_version()
        published_version = obj.publisher.get_published_version()
        if self.toolbar.edit_mode:
            if draft_version:
                # We're in edit mode. There is a draft article. Show the
                # publish button.
                self.add_publisher_publish_dropdown(draft_version)
            elif not published_version.publisher.has_pending_deletion_request:
                # We're in edit mode and there is no draft.
                # Add a edit button that will create a draft if it does not
                # exist.
                self.toolbar.add_button(
                    name='Edit and create',
                    url=onsite_url(published_version.get_draft_url()),
                    side=self.toolbar.RIGHT,
                    extra_classes=[
                        'cms-btn-action',
                    ],
                )
        elif published_version and published_version.publisher.has_pending_deletion_request:
            self.add_publisher_delete_dropdown(published_version)

    def add_publisher_publish_dropdown(self, obj):
        container = Dropdown(
            side=self.toolbar.RIGHT,
            extra_classes=[
                'cms-btn-action',
            ],
        )
        container.add_primary_button(
            Button(
                name=_('Publish'),
                url=onsite_url(obj.publisher.admin_urls.publish()),
                extra_classes=[
                    'cms-btn-action',
                ],
            )
        )
        container.buttons.append(
            Button(
                name=_('View published'),
                url=obj.get_absolute_url() + '?edit_off',
            )
        )
        container.buttons.append(
            Button(
                name=_('Discard draft'),
                url=onsite_url(obj.publisher.admin_urls.discard_draft()),
            )
        )
        container.buttons.append(
            Button(
                name=_('Request deletion'),
                url=onsite_url(obj.publisher.admin_urls.request_deletion()),
            )
        )
        self.toolbar.add_item(container)

    def add_publisher_delete_dropdown(self, obj):
        container = Dropdown(
            side=self.toolbar.RIGHT,
        )
        if obj.translations.count() <= 1:
            delete_url = onsite_url(obj.publisher.admin_urls.delete())
        else:
            delete_url = onsite_url(obj.publisher.admin_urls.delete_translation())
        container.add_primary_button(
            Button(
                name=_('Delete'),
                url=delete_url,
                extra_classes=[
                    'cms-btn-cation',
                ],
            )
        )
        container.buttons.append(
            Button(
                name=_('Discard deletion request'),
                url=onsite_url(obj.publisher.admin_urls.discard_deletion_request()),
            ),
        )
        self.toolbar.add_item(container)
