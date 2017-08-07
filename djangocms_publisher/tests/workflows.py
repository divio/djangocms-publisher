#-*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test.testcases import TestCase

from djangocms_publisher.test_project.test_app.models import Thing
from djangocms_publisher.test_project.test_app_parler.models import ParlerThing
from djangocms_publisher.utils.copying import refresh_from_db


class PublishTestCase(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_publish_thing(self):
        draft = Thing.objects.create(name='Test1')
        self.assertEqual(draft.publisher_is_draft_version, True)
        published = draft.publisher_publish()
        self.assertEqual(published.publisher_is_published_version, True)

        self.assertEqual(draft.name, published.name)
        # FIXME: Test actual fields and relationship updating


class ParlerTranslationPublishTestCase(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_publish_thing(self):
        draft = ParlerThing(a_boolean=True)
        draft.save()
        self.assertEqual(draft.publisher_is_draft_version, True)
        draft.translations.create(
            language_code='en',
            name='EN Translation',
        )
        draft.translations.create(
            language_code='de',
            name='EN Translation',
        )
        draft_de = draft.translations.get(language_code='de')
        self.assertEqual(draft_de.translation_publisher.is_draft_version, True)

        # Publish the de translation
        published_de = draft_de.translation_publisher.publish()

        self.assertEqual(published_de.translation_publisher.is_published_version, True)

        # Check that the name was correctly copied over
        self.assertEqual(draft_de.name, published_de.name)

        # Check that the master draft still exists
        # (there still is an untranslated 'en' version, so it needs to stay
        # around).
        self.assertEqual(ParlerThing.objects.filter(id=draft.pk).exists(), True)

        draft = refresh_from_db(draft)
        self.assertEqual(draft.publisher_is_draft_version, True)

        # Publish en translation
        draft_en = draft.translations.get(language_code='en')
        published_en = draft_en.translation_publisher.publish()

        self.assertEqual(published_en.translation_publisher.is_published_version, True)

        # Check that the name was correctly copied over
        self.assertEqual(draft_en.name, published_en.name)

        # Check that the master draft still exists
        # (there still is an untranslated 'en' version)
        self.assertEqual(ParlerThing.objects.filter(id=draft.pk).exists(), True)


        import ipdb;ipdb.set_trace()
        # FIXME: Test actual fields and relationship updating
