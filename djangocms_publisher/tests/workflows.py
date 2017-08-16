#-*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test.testcases import TestCase

from djangocms_publisher.test_project.test_app.models import (
    Thing,
    ThingAttachment,
    ExternalThing,
)
from djangocms_publisher.utils.copying import refresh_from_db


class PublishTestCase(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        Thing.objects.all().delete()
        Thing.objects.all().delete()

    def _create_draft(self, name, attachment_names=()):
        # Create first draft
        draft = Thing.objects.create(name=name)
        self.assertTrue(draft.publisher.is_draft_version)
        for name in attachment_names:
            draft.attachments.create(name=name)
        return draft

    def test_publisher_properties(self):
        draft = self._create_draft(name='Thing1')
        self.assertEqual(draft.publisher.is_published_version, draft.publisher_is_published_version)
        self.assertEqual(draft.publisher.is_draft_version, not draft.publisher_is_published_version)

        draft.publisher.is_published_version = True
        self.assertEqual(draft.publisher_is_published_version, True)

        draft.publisher.is_published_version = False
        self.assertEqual(draft.publisher_is_published_version, False)

        draft.publisher.is_draft_version = False
        self.assertEqual(draft.publisher_is_published_version, True)

        draft.publisher.is_draft_version = True
        self.assertEqual(draft.publisher_is_published_version, False)

    def test_full_workflow(self):
        attachment_names = ('att1', 'att2', 'att3')
        draft = self._create_draft(
            name='Test1',
            attachment_names=attachment_names,
        )

        self.assertEqual(Thing.objects.count(), 1)
        self.assertEqual(Thing.objects.publisher_drafts().count(), 1)
        self.assertEqual(Thing.objects.publisher_published().count(), 0)

        # Publish
        published = draft.publisher.publish()
        self.assertEqual(Thing.objects.count(), 1)
        self.assertEqual(Thing.objects.publisher_drafts().count(), 0)
        self.assertEqual(Thing.objects.publisher_published().count(), 1)
        self.assertTrue(published.publisher.is_published_version)
        self.assertEqual(draft.name, published.name)
        self.assertEqual(
            set(published.attachments.values_list('name', flat=True)),
            set(attachment_names),
        )
        self.assertFalse(Thing.objects.filter(publisher_published_version=published).exists())

        # Create draft again
        published = refresh_from_db(published)
        draft = published.publisher.create_draft()
        self.assertEqual(Thing.objects.count(), 2)
        self.assertEqual(Thing.objects.publisher_drafts().count(), 1)
        self.assertEqual(Thing.objects.publisher_published().count(), 1)
        self.assertEqual(Thing.objects.publisher_draft_or_published_only().count(), 1)
        draft = refresh_from_db(draft)
        self.assertEqual(draft.publisher_published_version, published)
        self.assertTrue(draft.publisher.is_draft_version)
        self.assertEqual(draft.name, published.name)

        # Edit the draft
        new_draft_name = 'Test2 altered'
        draft = refresh_from_db(draft)
        draft.name = new_draft_name
        draft.save()

        # Publish draft again
        published = draft.publisher.publish()
        published = refresh_from_db(published)
        self.assertEqual(Thing.objects.count(), 1)
        self.assertEqual(new_draft_name, published.name)

    def test_discard(self):
        draft = self._create_draft(name='Test discard', attachment_names=('one', 'two',))
        draft_id = draft.id
        draft.publisher.discard_draft()
        self.assertFalse(Thing.objects.filter(id=draft_id).exists())

    def test_discard_with_published(self):
        draft = self._create_draft(name='Test discard', attachment_names=('one', 'two',))
        published = draft.publisher.publish()
        draft = published.publisher.create_draft()
        draft_id = draft.id
        published_id = published.id
        draft.publisher.discard_draft()
        self.assertFalse(Thing.objects.filter(id=draft_id).exists())
        self.assertTrue(Thing.objects.filter(id=published_id).exists())

    def test_update_relations(self):
        thing_draft = self._create_draft('a Thing', attachment_names=('att1', 'att2'))
        thing_published = thing_draft.publisher.publish(delete=False, update_relations=False)
        thing_published_id1 = thing_published.id

        external_thing = ExternalThing.objects.create(name='ext thing', thing=thing_draft)
        external_thing.things = [thing_draft]
        external_thing = refresh_from_db(external_thing)
        self.assertEqual(external_thing.things.count(), 1)

        self.assertEqual(external_thing.thing, thing_draft)
        self.assertEqual(external_thing.things.first(), thing_draft)

        thing_draft = refresh_from_db(thing_draft)
        thing_published = thing_draft.publisher.publish()
        thing_published_id2 = thing_published.id
        self.assertEqual(thing_published_id1, thing_published_id2)
        external_thing = refresh_from_db(external_thing)
        self.assertEqual(external_thing.thing, thing_published)
        self.assertEqual(external_thing.things.first(), thing_published)


