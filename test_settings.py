# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os


def gettext(s):
    return s


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HELPER_SETTINGS = {
    'NOSE_ARGS': [
        '-s',
    ],
    'ROOT_URLCONF': 'djangocms_publisher.test_project.urls',
    'INSTALLED_APPS': [
        'parler',
        'djangocms_publisher',
        'djangocms_publisher.test_project.test_app',
        'djangocms_publisher.test_project.test_app_parler',
    ],
    'LANGUAGE_CODE': 'en',
    'LANGUAGES': (
        ('en', gettext('English')),
        ('fr-fr', gettext('French')),
        ('de', gettext('Italiano')),
    ),
    'CMS_LANGUAGES': {
        1: [
            {
                'code': 'en',
                'name': gettext('English'),
                'public': True,
            },
            {
                'code': 'de',
                'name': gettext('German'),
                'public': True,
            },
            {
                'code': 'fr-fr',
                'name': gettext('French'),
                'public': True,
            },
        ],
        'default': {
            'hide_untranslated': False,
        },
    },
}


def run():
    from djangocms_helper import runner
    runner.run('djangocms_publisher')


if __name__ == "__main__":
    run()
