# -*- coding: utf-8 -*-
from __future__ import unicode_literals


from django.db import models
from django.db.models import Q
from django.utils.encoding import python_2_unicode_compatible, force_text
from djangocms_publisher.models import (
    PublisherQuerySetMixin,
)
from djangocms_publisher.contrib.parler.models import (
    ParlerPublisherModelMixin,
    ParlerPublisherTranslatedFields,
)
from parler.models import TranslatableModel
from parler.managers import TranslatableQuerySet


class ParlerThingQuerySet(PublisherQuerySetMixin, TranslatableQuerySet):
    def search(self, term):
        return self.filter(
            Q(name__icontains=term) |
            Q(description__icontains=term)
        )


@python_2_unicode_compatible
class ParlerThing(ParlerPublisherModelMixin, TranslatableModel):
    a_boolean = models.BooleanField(blank=True, default=False)

    related_things = models.ManyToManyField('self', symmetrical=False)
    related_things_symmetrical = models.ManyToManyField('self', symmetrical=True)

    many_to_many_attachments = models.ManyToManyField('ThingAttachment', blank=True)

    translations = ParlerPublisherTranslatedFields(
        name=models.CharField(max_length=255)
        # TODO: test other fields/relations on the translated model
    )

    objects = ParlerThingQuerySet.as_manager()

    def __str__(self):
        return force_text(self.id)
        return self.publisher.add_status_label(
            super(ParlerThing, self).__str__()
        )

    def can_publish(self):
        assert self.is_draft
        # FOR SUBCLASSES
        # Checks whether the data and all linked data is ready to publish.
        # Raise ValidationError if not.

    def user_can_publish(self, user):
        # FOR SUBCLASSES
        # Checks whether the user has permissions to publish
        return True

    def publisher_copy_relations(self, old_obj):
        # ManyToManyFields
        self.many_to_many_attachments = old_obj.many_to_many_attachments.all()
        self.related_things = old_obj.related_things.all()
        self.related_things_symmetrical = old_obj.related_things_symmetrical.all()

        # ForeignKeys pointing to this obj
        self.attachments.all().delete()
        for attachment in old_obj.attachments.all():
            attachment.id = attachment.pk = None
            attachment.thing = self
            attachment.save()


class ThingAttachment(models.Model):
    thing = models.ForeignKey(ParlerThing, related_name='attachments')
    name = models.CharField(max_length=255)
