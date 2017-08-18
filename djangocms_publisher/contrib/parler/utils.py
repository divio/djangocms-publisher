# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from parler import appsettings
from parler.utils.views import TabsList
from parler.utils import normalize_language_code, is_multilingual_project, get_language_title


from django.core.urlresolvers import reverse


class Tab(object):
    def __init__(self, url, title, code, status, publisher_state):
        self.url = url
        self.title = title
        self.code = code
        self.status = status
        self.publisher_state = publisher_state


def get_admin_change_url_for_translation(translation, get):
    obj = translation.master
    opts = obj._meta
    url_name = 'admin:%s_%s_%s' % (opts.app_label, opts.model_name, 'change')
    get['language'] = translation.language_code
    return reverse(
        url_name,
        args=[translation.master_id]
    ) + '?{0}'.format(get.urlencode())


def get_language_tabs(request, obj, current_language, available_languages, css_class=None):
    """
    Determine the language tabs to show.
    """
    tabs = TabsList(css_class=css_class)
    tab_languages = []
    if obj and obj.pk:
        is_draft_version = obj.publisher.is_draft_version
        all_translations = (
            obj.publisher
            .all_translations_dict(prefer_drafts=is_draft_version)
        )
    else:
        is_draft_version = True
        all_translations = {}
    site_id = getattr(settings, 'SITE_ID', None)
    for lang_dict in appsettings.PARLER_LANGUAGES.get(site_id, ()):
        code = lang_dict['code']
        title = get_language_title(code)
        get = request.GET.copy()
        get['language'] = code
        translation = all_translations.get(code)
        if translation:
            url = get_admin_change_url_for_translation(translation, get)
            publisher_state = translation.publisher.state
        else:
            # No translation yet. We want to show a link to create a
            # translation.
            url = '?{0}'.format(get.urlencode())
            publisher_state = get_empty_publisher_state(code)

        if code == current_language:
            status = 'current'
        elif code in all_translations.keys():
            status = 'available'
        else:
            status = 'empty'
        tabs.append(
            Tab(
                url=url,
                title=title,
                code=code,
                status=status,
                publisher_state=publisher_state
            )
        )
        tab_languages.append(code)

    # # Additional stale translations in the database?
    # if appsettings.PARLER_SHOW_EXCLUDED_LANGUAGE_TABS:
    #     for code in available_languages:
    #         if code not in tab_languages:
    #             get['language'] = code
    #             url = '?{0}'.format(get.urlencode())
    #
    #             if code == current_language:
    #                 status = 'current'
    #             else:
    #                 status = 'available'
    #
    #             tabs.append((url, get_language_title(code), code, status))

    tabs.current_is_translated = current_language in all_translations.keys()
    # FIXME: show correct deletion possibilities based on publisher state
    # tabs.allow_deletion = len(available_languages) > 1
    tabs.allow_deletion = True
    return tabs


def get_empty_publisher_state(language_code):
    return {
        'identifier': 'empty',
        'css_class': 'empty',
        'text': _('Does not exist'),
        'language_code': language_code,
    }
