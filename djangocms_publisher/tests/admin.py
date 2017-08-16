#-*- coding: utf-8 -*-
from __future__ import absolute_import

from django.core.urlresolvers import reverse
from django.test import TestCase
from . import helpers
from ..test_project.test_app.models import Thing


class PublisherAdminUrlsTests(TestCase):
    def setUp(self):
        self.superuser = helpers.create_superuser()
        self.client.login(username='admin', password='secret')

    def tearDown(self):
        self.client.logout()
        Thing.objects.all().delete()

    def test_app_index_get(self):
        response = self.client.get(reverse('admin:app_list', args=('test_app',)))
        self.assertEqual(response.status_code, 200)

    def test_change_list_get(self):
        obj = Thing.objects.create(name='Test thing')
        info = obj._meta.app_label, obj._meta.model_name
        return reverse('admin:{}_{}_changelist'.format(*info))

    def test_change_get(self, obj=None):
        obj = Thing.objects.create(name='Test thing')
        info = obj._meta.app_label, obj._meta.model_name
        response = self.client.get(reverse('admin:{}_{}_change'.format(*info), args=(obj.pk,)))
        self.assertEqual(response.status_code, 200)
