#-*- coding: utf-8 -*-
from __future__ import absolute_import

from django.core.exceptions import ObjectDoesNotExist
from django.test.testcases import TestCase

from djangocms_publisher.test_project.test_app.models import Thing
from djangocms_publisher.test_project.test_app_parler.models import ParlerThing
from djangocms_publisher.utils.copying import refresh_from_db


class ParlerTranslationPublishTestCase(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_publish_from_draft(self):
        draft = ParlerThing()
        draft.save()
        self.assertTrue(draft.master_publisher.is_draft_version)
        draft.translations.create(
            language_code='en',
            name='EN Translation',
        )
        draft.translations.create(
            language_code='de',
            name='DE Translation',
        )
        translation_draft_de = draft.translations.get(language_code='de')
        self.assertTrue(translation_draft_de.publisher.is_draft_version)

        draft_de = refresh_from_db(draft)
        draft_de.set_current_language('de')

        self.assertTrue(draft_de.publisher.is_draft_version)

        # Publish the de translation
        published_de = draft_de.publisher.publish()

        self.assertTrue(published_de.publisher.is_published_version)

        # Check that the name was correctly copied over
        self.assertEqual(draft_de.name, published_de.name)

        # Check that the master draft still exists
        # (there still is an untranslated 'en' version, so it needs to stay
        # around).
        self.assertTrue(ParlerThing.objects.filter(id=draft.pk).exists())

        draft = refresh_from_db(draft)
        self.assertFalse(draft.publisher_is_published_version)

        # Publish en translation
        draft_en = refresh_from_db(draft)
        draft_en.set_current_language('en')
        published_en = draft_en.publisher.publish()

        self.assertTrue(published_en.publisher.is_published_version)

        # Check that the name was correctly copied over
        self.assertEqual(draft_en.name, published_en.name)

        # Check that the master draft has been deleted
        # (no more draft translations exist)
        self.assertFalse(ParlerThing.objects.filter(id=draft.pk).exists())
        self.assertFalse(published_en.publisher.has_pending_changes)
        self.assertFalse(published_en.master_publisher.has_pending_changes)

        # FIXME: Test actual fields and relationship updating

    def test_create_draft(self):
        published = ParlerThing(publisher_is_published_version=True)
        published.save()
        self.assertTrue(published.publisher_is_published_version)
        self.assertTrue(published.master_publisher.is_published_version)
        published.translations.create(
            language_code='en',
            name='EN Translation',
        )
        published.translations.create(
            language_code='de',
            name='DE Translation',
        )
        published_translation_de = published.translations.get(language_code='de')
        self.assertTrue(published_translation_de.publisher.is_published_version)
        self.assertTrue(published_translation_de.master.publisher_is_published_version)

        # Create draft translation
        published_de = refresh_from_db(published)
        published_de.set_current_language('de')

        draft_de = published_de.publisher.create_draft()

        self.assertEqual(draft_de.language_code, 'de')

        draft_de = refresh_from_db(draft_de)
        draft_de.set_current_language('de')
        published_de = refresh_from_db(published_de)
        published_de.set_current_language('de')

        self.assertTrue(draft_de.publisher.is_draft_version)
        self.assertFalse(draft_de.publisher_is_published_version)
        self.assertEqual(
            draft_de.publisher_published_version_id,
            published_de.id
        )
        self.assertEqual(
            draft_de.get_translation('de').publisher.get_published_version(),
            published_translation_de,
        )
        # Check that the name was correctly copied over
        self.assertEqual(draft_de.name, published_de.name)
        self.assertEqual(
            draft_de.get_translation('de').name,
            published_de.get_translation('de').name,
        )

    # def test_request_translation_deletion(self):
    #     published = ParlerThing(publisher_is_published_version=True)
    #     published.save()
    #     published.translations.create(
    #         language_code='en',
    #         name='EN Translation',
    #     )
    #     published.translations.create(
    #         language_code='de',
    #         name='DE Translation',
    #     )
    #     published_de = published.translations.get(language_code='de')
    #
    #     self.assertFalse(published_de.translation_publisher.has_pending_deletion_request)
    #     # Request deletion
    #     published_de = published_de.translation_publisher.request_deletion()
    #     self.assertTrue(published_de.translation_publisher.has_pending_deletion_request)
    #
    # def test_request_translation_deletion_with_existing_draft(self):
    #     published = ParlerThing(publisher_is_published_version=True)
    #     published.save()
    #     published.translations.create(
    #         language_code='en',
    #         name='EN Translation',
    #     )
    #     published.translations.create(
    #         language_code='de',
    #         name='DE Translation',
    #     )
    #     published_de = published.translations.get(language_code='de')
    #     draft_de = published_de.translation_publisher.create_draft()
    #     # FIXME: We have to refresh from db here to get valid data. Should we
    #     #        do this in the code to, or just here in the tests?
    #     published_de = refresh_from_db(published_de)
    #     # FIXME: why the hell does this only work if I refresh the draft from db?
    #     draft_de = refresh_from_db(draft_de)
    #     self.assertTrue(draft_de.translation_publisher.has_pending_changes)
    #     self.assertTrue(published_de.translation_publisher.has_pending_changes)
    #     self.assertFalse(published_de.translation_publisher.has_pending_deletion_request)
    #
    #     # Request deletion
    #     published_de = draft_de.translation_publisher.request_deletion()
    #
    #     self.assertRaises(ObjectDoesNotExist, lambda: refresh_from_db(draft_de))
    #     self.assertTrue(published_de.translation_publisher.has_pending_deletion_request)
    #
    #     published_de = refresh_from_db(published_de)
    #     draft_de_exists = bool(published_de.translation_publisher.get_draft_version())
    #     self.assertFalse(draft_de_exists)
