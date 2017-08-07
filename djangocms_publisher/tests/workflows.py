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

    def test_publish_from_draft(self):
        draft = ParlerThing(a_boolean=True)
        draft.save()
        self.assertTrue(draft.publisher_is_draft_version)
        draft.translations.create(
            language_code='en',
            name='EN Translation',
        )
        draft.translations.create(
            language_code='de',
            name='EN Translation',
        )
        draft_de = draft.translations.get(language_code='de')
        self.assertTrue(draft_de.translation_publisher.is_draft_version)

        # Publish the de translation
        published_de = draft_de.translation_publisher.publish()

        self.assertTrue(published_de.translation_publisher.is_published_version)

        # Check that the name was correctly copied over
        self.assertEqual(draft_de.name, published_de.name)

        # Check that the master draft still exists
        # (there still is an untranslated 'en' version, so it needs to stay
        # around).
        self.assertTrue(ParlerThing.objects.filter(id=draft.pk).exists())

        draft = refresh_from_db(draft)
        self.assertTrue(draft.publisher_is_draft_version)

        # Publish en translation
        draft_en = draft.translations.get(language_code='en')
        published_en = draft_en.translation_publisher.publish()

        self.assertTrue(published_en.translation_publisher.is_published_version)

        # Check that the name was correctly copied over
        self.assertEqual(draft_en.name, published_en.name)

        # Check that the master draft has been deleted
        # (no more draft translations exist)
        self.assertFalse(ParlerThing.objects.filter(id=draft.pk).exists())
        self.assertFalse(published_en.master.publisher_has_pending_changes)

        # FIXME: Test actual fields and relationship updating

    def test_create_draft(self):
        published = ParlerThing(a_boolean=True, publisher_is_published_version=True)
        published.save()
        self.assertTrue(published.publisher_is_published_version)
        published.translations.create(
            language_code='en',
            name='EN Translation',
        )
        published.translations.create(
            language_code='de',
            name='EN Translation',
        )
        published_de = published.translations.get(language_code='de')
        self.assertTrue(published.publisher_is_published_version)
        self.assertTrue(published_de.translation_publisher.is_published_version)

        # Create draft translation
        draft_de = published_de.translation_publisher.create_draft()

        self.assertTrue(draft_de.translation_publisher.is_draft_version)

        # Check that the name was correctly copied over
        self.assertEqual(draft_de.name, published_de.name)
