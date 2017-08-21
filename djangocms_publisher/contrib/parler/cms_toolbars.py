# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import json

from django.conf import settings

from cms.toolbar_pool import toolbar_pool
from cms.constants import REFRESH_PAGE
from cms.toolbar.items import Dropdown, DropdownToggleButton, ModalButton, \
    Button, BaseButton
from cms.utils import get_cms_setting

from django.utils.translation import (
    ugettext as _, get_language_from_request, override)

from cms.toolbar_base import CMSToolbar
from djangocms_publisher.utils.copying import refresh_from_db


class AjaxButton(BaseButton):
    template = 'admin/djangocms_publisher/toolbar/ajax_button.html'

    def __init__(self, name, action, data, question=None, active=False, disabled=False, extra_classes=None):
        self.name = name
        self.action = action
        self.question = question
        self.active = active
        self.disabled = disabled
        self.data = data
        self.on_success = REFRESH_PAGE
        self.extra_classes = extra_classes or []

    def get_context(self):
        return {
            'name': self.name,
            'active': self.active,
            'disabled': self.disabled,
            'data': json.dumps(self.data),
            'action': self.action,
            'question': self.question,
            'on_success': self.on_success,
            'extra_classes': self.extra_classes,
        }


class LanguageAjaxButton(AjaxButton):
    template = 'admin/djangocms_publisher/toolbar/language_ajax_button.html'

    def __init__(self, *args, **kwargs):
        self.state = kwargs.pop('state')
        super(LanguageAjaxButton, self).__init__(*args, **kwargs)

    def get_context(self):
        context = super(LanguageAjaxButton, self).get_context()
        context['state'] = self.state
        return context


class LanguageButton(Button):
    template = 'admin/djangocms_publisher/toolbar/language_button.html'

    def __init__(self, *args, **kwargs):
        self.state = kwargs.pop('state')
        super(LanguageButton, self).__init__(*args, **kwargs)

    def get_context(self):
        context = super(LanguageButton, self).get_context()
        context['state'] = self.state
        return context


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
    publisher_disable_core_draft_live = True

    def setup_publisher_toolbar(self, obj):
        draft_version = obj.publisher.get_draft_version()
        published_version = obj.publisher.get_published_version()
        if self.toolbar.edit_mode:
            if draft_version:
                # We're in edit mode. There is a draft article. Show the
                # publish button.
                self.add_publisher_publish_dropdown(draft_version)
            # elif not published_version.publisher.has_pending_deletion_request:
            #     # We're in edit mode and there is no draft.
            #     # Add a edit button that will create a draft if it does not
            #     # exist.
            #     self.add_create_draft_button(published_version)
        else:
            if published_version and published_version.publisher.has_pending_deletion_request:
                self.add_publisher_delete_dropdown(published_version)
            # elif published_version and not draft_version:
            #     self.add_create_draft_button(published_version)
            # elif draft_version:
            #     self.add_change_draft_button(draft_version)
        if (
            (self.toolbar.edit_mode and not draft_version and not published_version.publisher.has_pending_deletion_request) or
            (not self.toolbar.edit_mode and published_version and not published_version.publisher.has_pending_deletion_request)
        ):
            self.add_edit_button(obj)

    def get_language_buttons(self, obj):
        buttons = []
        all_languages = dict(settings.LANGUAGES)
        for translation in obj.publisher.all_translations(prefer_drafts=True):
            draft_translation = translation.publisher.get_draft_version()
            if draft_translation:
                btn = LanguageButton(
                    name=all_languages.get(translation.language_code),
                    url=onsite_url(
                        '{}?{}'.format(
                            obj.get_draft_url(language=obj.language_code),
                            get_cms_setting('CMS_TOOLBAR_URL__EDIT_ON'),
                        )
                    ),
                    state=draft_translation.publisher.state,
                )
            else:
                published = translation.publisher.aware_master
                # btn = LanguageAjaxButton(
                #     name=all_languages.get(translation.language_code),
                #     action=onsite_url(published.publisher.admin_urls.create_draft()),
                #     data={'csrfmiddlewaretoken': self.toolbar.csrf_token},
                #     state=translation.publisher.state,
                # )
                btn = LanguageButton(
                    name=all_languages.get(translation.language_code),
                    url=onsite_url(published.publisher.admin_urls.create_draft()),
                    state=published.publisher.state,
                )

            buttons.append(btn)
        return buttons

    def add_edit_button(self, obj):
        draft = obj.publisher.get_draft_version()
        if draft:
            primary_button = self.get_change_draft_button(draft)
        else:
            primary_button = self.get_create_draft_button(obj)
        container = Dropdown(
            side=self.toolbar.RIGHT,
            extra_classes=[
                'cms-btn-action',
            ],
        )
        container.add_primary_button(primary_button)
        container.buttons.extend(self.get_language_buttons(obj))
        self.toolbar.add_item(container)

    def get_create_draft_button(self, obj):
        return Button(
            name='Edit',
            url=onsite_url(obj.publisher.admin_urls.create_draft()),
            extra_classes=[
                'cms-btn-action',
            ],
        )

    def get_change_draft_button(self, obj):
        return Button(
            name='Edit',
            url=onsite_url(
                '{}?{}'.format(
                    obj.get_draft_url(language=obj.language_code),
                    get_cms_setting('CMS_TOOLBAR_URL__EDIT_ON'),
                )
            ),
            extra_classes=[
                'cms-btn-action',
            ],
        )

    # def add_create_draft_button(self, obj):
    #     self.toolbar.add_button(
    #         name='Edit+',
    #         url=onsite_url(obj.publisher.admin_urls.create_draft()),
    #         side=self.toolbar.RIGHT,
    #         extra_classes=[
    #             'cms-btn-action',
    #         ],
    #     )
    #
    # def add_change_draft_button(self, obj):
    #     self.toolbar.add_button(
    #         name='Edit',
    #         url=onsite_url(
    #             '{}?{}'.format(
    #                 obj.get_draft_url(language=obj.language_code),
    #                 get_cms_setting('CMS_TOOLBAR_URL__EDIT_ON'),
    #             )
    #         ),
    #         side=self.toolbar.RIGHT,
    #         extra_classes=[
    #             'cms-btn-action',
    #         ],
    #     )

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
            # AjaxButton(
            #     name=_('Publish'),
            #     action=onsite_url(obj.publisher.admin_urls.publish()),
            #     data={'csrfmiddlewaretoken': self.toolbar.csrf_token},
            #     extra_classes=[
            #         'cms-btn-action',
            #     ],
            # )
        )
        container.buttons.append(
            Button(
                name=_('View published'),
                url=obj.get_public_url(language=obj.language_code) + '?edit_off',
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

        container.buttons.extend(self.get_language_buttons(obj))

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


try:
    PageToolbar = toolbar_pool.toolbars['cms.cms_toolbars.PageToolbar']
except:
    from cms.cms_toolbars import PageToolbar


class PublisherNoDraftLiveButtonsPageToolbar(PageToolbar):
    def post_template_populate(self):
        self.init_placeholders()
        show_core_draft_live = True
        for toolbar in self.toolbar.toolbars.values():
            if toolbar.is_current_app and getattr(toolbar, 'publisher_disable_core_draft_live', False):
                show_core_draft_live = False
                break
        if show_core_draft_live:
            self.add_draft_live()
        self.add_publish_button()
        self.add_structure_mode()


toolbar_pool.toolbars['cms.cms_toolbars.PageToolbar'] = PublisherNoDraftLiveButtonsPageToolbar
