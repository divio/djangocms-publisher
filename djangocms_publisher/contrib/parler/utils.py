# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from functools import partial

from django.conf import settings
from django.http import QueryDict
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from parler.utils.views import TabsList
from parler.utils import get_language_title


from django.core.urlresolvers import reverse


class Tab(object):
    def __init__(self, url, title, code, status, publisher_state):
        self.url = url
        self.title = title
        self.code = code
        self.status = status
        self.publisher_state = publisher_state


def get_admin_change_url_for_translation(translation, get):
    if get is None:
        get = QueryDict()
    get = get.copy()
    opts = translation.master._meta
    url_name = 'admin:%s_%s_%s' % (opts.app_label, opts.model_name, 'change')
    get['language'] = translation.language_code
    return reverse(
        url_name,
        args=[translation.master_id]
    ) + '?{0}'.format(get.urlencode())


def get_admin_change_url(obj, language_code=None, get=None):
    if get is None:
        get = QueryDict()
    get = get.copy()
    if language_code:
        get['language'] = language_code
    opts = obj._meta
    url_name = 'admin:%s_%s_%s' % (opts.app_label, opts.model_name, 'change')
    return reverse(
        url_name,
        args=[obj.id]
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
    from pprint import pprint as pp
    pp(all_translations)
    all_language_codes = [code for code, name in settings.LANGUAGES]
    for code in all_language_codes:
        title = get_language_title(code)
        get = request.GET.copy()
        get['language'] = code
        translation = all_translations.get(code)
        if translation:
            print translation.language_code, translation.master_id
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

    tabs.current_is_translated = current_language in all_translations.keys()
    # We have the delete ui in the submit row.
    tabs.allow_deletion = False
    return tabs


def get_empty_publisher_state(language_code):
    return {
        'identifier': 'empty',
        'css_class': 'empty',
        'text': _('Does not exist'),
        'language_code': language_code,
    }


def publisher_translation_state_for_language(obj, **kwargs):
    language_code = kwargs['language_code']
    states = obj.publisher.translation_states_dict()
    return render_to_string(
        'admin/djangocms_publisher/tools/status_indicator.html',
        context={'state': states.get(language_code)}
    )


def publisher_translation_states_admin_fields(admin):
    languages = [code for code, name in settings.LANGUAGES]
    for language_code in languages:
        code = language_code.lower().replace('-', '_')
        name = 'publisher_translation_state_{}'.format(code)
        method = partial(
            publisher_translation_state_for_language,
            language_code=code,
        )
        method.allow_tags = True
        method.short_description = code.upper()
        setattr(admin, name, method)


def publisher_translation_states_admin_field_names():
    language_codes = [code for code, name in settings.LANGUAGES]
    return [
        publisher_translation_states_admin_field_name(code)
        for code in language_codes
    ]


def publisher_translation_states_admin_field_name(language_code):
    language_code = language_code.lower().replace('-', '_')
    return 'publisher_translation_state_{}'.format(language_code)
