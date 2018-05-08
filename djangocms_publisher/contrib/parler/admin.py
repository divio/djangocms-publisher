# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.admin.utils import unquote
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import Http404, HttpResponseRedirect, QueryDict
from django.template.loader import render_to_string

from . import utils
from ...admin import AdminUrls, PublisherAdminMixinBase


class ParlerAdminUrls(AdminUrls):
    def get_url(self, name, get=None, args=None, language=None):
        if get is None:
            get = QueryDict()
        get = get.copy()
        if language is not None:
            get['language'] = language
        else:
            get['language'] = self.instance.language_code
        return super(ParlerAdminUrls, self).get_url(name=name, get=get)

    def delete_translation(self, **kwargs):
        return super(ParlerAdminUrls, self).get_url(
            name='delete_translation',
            args=[self.instance.pk, self.instance.language_code],
        )


class PublisherParlerAdminMixin(PublisherAdminMixinBase):
    def has_delete_permission(self, request, obj=None):
        if obj and obj.pk and obj.publisher.is_published_version:
            if (
                (
                    obj.publisher.has_pending_deletion_request or
                    obj.translations.count() == 1 and
                    obj.translations.filter(publisher_translation_deletion_requested=True).exists()
                ) and
                self.has_publish_permission(request, obj)
            ):
                return True
            return False
        elif obj and obj.pk and obj.publisher.is_draft_version and obj.publisher.has_published_version:
            return False
        return (
            super(PublisherParlerAdminMixin, self)
            .has_delete_permission(request, obj)
        )

    @property
    def change_form_template(self):
        return 'admin/djangocms_publisher/contrib/parler/parler_publisher_change_form.html'

    def get_language_tabs(self, request, obj, available_languages, css_class=None):
        current_language = self.get_form_language(request, obj)
        return utils.get_language_tabs(
            request,
            obj=obj,
            current_language=current_language,
            available_languages=available_languages,
            css_class=css_class,
        )

    def publisher_get_buttons(self, request, obj):
        buttons = (
            super(PublisherParlerAdminMixin, self)
            .publisher_get_buttons(request, obj)
        )
        language_code = request.GET.get('language_code')
        if not language_code:
            language_code = getattr(obj, 'language_code', None)

        published_waiting_for_deletion = (
            obj and
            obj.publisher.is_published_version and
            obj.publisher.has_pending_deletion_request
        )
        draft_without_any_published = (
            obj and
            obj.publisher.is_draft_version and
            not obj.master_publisher.get_published_version()
        )

        if (
            (
                published_waiting_for_deletion or draft_without_any_published
            ) and
            language_code and
            obj.translations.count() > 1 and
            'delete' in buttons
        ):
            # Show the language specific delete view if there still is any
            # language around.
            btn = buttons.get('delete')
            btn['url'] = obj.publisher.admin_urls.delete_translation()
            btn['label'] = '{} ({})'.format(
                btn['label'],
                language_code.upper(),
            )
        return buttons

    def response_delete(self, request, obj_display, obj_id):
        if request.GET.get('redirect') == 'onsite':
            # TODO: Anything better we can do?
            return HttpResponseRedirect('/')
        return (
            super(PublisherParlerAdminMixin, self)
            .response_delete(request, obj_display, obj_id)
        )

    def delete_translation(self, request, object_id, language_code):
        root_model = self.model._parler_meta.root_model
        try:
            translation = root_model.objects.get(master_id=unquote(object_id), language_code=language_code)
        except root_model.DoesNotExist:
            raise Http404

        # These are needed for the redirect later on.
        master_draft = (
            translation
            .master
            .master_publisher
            .get_draft_version()
        )
        master_published = (
            translation
            .master
            .master_publisher
            .get_published_version()
        )
        master_pks = set()
        if master_draft:
            master_pks.add(master_draft.pk)
        if master_published:
            master_pks.add(master_published.pk)
        # /

        is_published_version_and_deletion_already_requested = (
            translation.publisher.is_published_version and
            translation.publisher.has_pending_deletion_request
        )
        is_draft_version_and_no_published_version_exists = (
            translation.publisher.is_draft_version and
            not translation.publisher.has_published_version
        )
        if (
            is_published_version_and_deletion_already_requested or
            is_draft_version_and_no_published_version_exists
        ):
            # In this case we show the normal delete view because we'll actually
            # want to delete the object for real.
            if not self.has_publish_permission(request, translation):
                # TODO: Show a message about denied permission instead?
                raise PermissionDenied
            response = (
                super(PublisherParlerAdminMixin, self)
                .delete_translation(request, object_id, language_code)
            )
            if request.method == 'POST' and response.status_code == 302:
                # The translation has been deleted. Lets figure out a good place
                # to redirect to.
                onsite = request.GET.get('redirect') == 'onsite'
                obj = (
                    self.model.objects
                    .filter(pk__in=master_pks)
                    .order_by('-publisher_is_published_version')
                    .first()
                )
                if obj:
                    if onsite:
                        return HttpResponseRedirect(obj.get_absolute_url())
                    else:
                        return HttpResponseRedirect(obj.master_publisher.admin_urls.change())
                else:
                    if onsite:
                        # TODO: anything better we can do?
                        return HttpResponseRedirect('/')
                    else:
                        return HttpResponseRedirect(self.publisher_get_admin_changelist_url())
            return response
        # This means it is a draft or published object that needs a deletion
        # request before it can be deleted.
        raise PermissionDenied

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = (
            super(PublisherParlerAdminMixin, self)
            .get_readonly_fields(request, obj=obj)
        )
        if not obj or obj and not obj.publisher_is_published_version:
            return readonly_fields
        readonly_fields = set(readonly_fields)
        readonly_fields |= set(obj._parler_meta.get_translated_fields())
        return list(readonly_fields)

    def publisher_get_admin_changelist_url(self, obj=None, get=None):
        from parler.models import TranslatedFieldsModel
        is_parler_translation = isinstance(obj, TranslatedFieldsModel)
        if is_parler_translation:
            # The url should needs to use the id of the master object.
            # and the language does not matter anymore.
            master = obj.master
        else:
            master = obj
        return (
            super(PublisherParlerAdminMixin, self)
            .publisher_get_admin_changelist_url(master, get=get)
        )

    def publisher_get_detail_admin_url(self, obj, get=None):
        try:
            translation = obj.get_translation(obj.language_code)
        except ObjectDoesNotExist:
            # FIXME: This should not happen. But it does. Seems to try to get
            #        the default language sometimes. And if that does not exist
            #        it goes boom.
            return (
                utils
                .get_admin_change_url(
                    obj,
                    language_code=obj.language_code,
                    get=get,
                ))
        return utils.get_admin_change_url_for_translation(translation, get=get)

    def publisher_get_status_field_context(self, obj):
        return {
            'state': obj.master_publisher.state,
        }

    def publisher_translation_states(self, obj):
        return render_to_string(
            'admin/djangocms_publisher/tools/status_label_parler_all.html',
            context={
                'states': obj.publisher.translation_states,
            },
        )
    publisher_translation_states.allow_tags = True
    publisher_translation_states.short_description = 'EN DE FR'

    def publisher_state_debug(self, obj):
        return render_to_string(
            'admin/djangocms_publisher/contrib/parler/debug/state_debug.html',
            context={'obj': obj},
        )
    publisher_state_debug.allow_tags = True
    publisher_state_debug.short_description = 'publisher state debug'


utils.publisher_translation_states_admin_fields(
    admin=PublisherParlerAdminMixin,
)
