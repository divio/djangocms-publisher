# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.http import HttpResponseRedirect, Http404, QueryDict
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.utils.encoding import force_text
from ...admin import PublisherAdminMixinBase, get_all_button_defaults, AdminUrls
from . import utils, admin_views


class ParlerAdminUrls(AdminUrls):
    def get_url(self, name, get=None, args=None):
        if get is None:
            get = QueryDict()
        get = get.copy()
        get['language'] = self.instance.language_code
        return super(ParlerAdminUrls, self).get_url(name=name, get=get)

    # def create_draft(self, **kwargs):
    #     # Because django-cms toolbar just adds ?edit
    #     # onto the url instead of checking if the url already has get params
    #     # and use &edit instead, we're forced to put the language into the
    #     # url instead of a get param for this view.
    #     # Intentionally skipping get_url from self, because we don't want the
    #     # language code as get param in this case.
    #     return super(ParlerAdminUrls, self).get_url(
    #         name='publisher_create_draft',
    #         args=[self.instance.pk, self.instance.language_code],
    #     )

    def delete_translation(self, **kwargs):
        return super(ParlerAdminUrls, self).get_url(
            name='delete_translation',
            args=[self.instance.pk, self.instance.language_code],
        )


class PublisherParlerAdminMixin(PublisherAdminMixinBase):
    # delete_confirmation_template = 'admin/djangocms_publisher/contrib/parler/translation_delete_request_confirmation.html'

    # def publisher_get_urls(self):
    #     urls = super(PublisherParlerAdminMixin, self).publisher_get_urls()
    #     return [
    #         self.publisher_get_action_urlpattern_with_language(admin_views.CreateDraft),
    #     ] + urls
    #
    # def publisher_get_action_urlpattern_with_language(self, view):
    #     opts = self.model._meta
    #     url_segment = view.action_name.replace('_', '-')
    #     url_name = '{0}_{1}_publisher_{2}'.format(
    #         opts.app_label,
    #         opts.model_name,
    #         view.action_name,
    #     )
    #     return url(
    #         r'^(?P<pk>.+)/' + url_segment + r'/(?P<language>[a-zA-Z_-]*)/$',
    #         self.admin_site.admin_view(view.as_view(admin=self)),
    #         name=url_name,
    #     )

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
        if 'delete' in buttons and obj and obj.publisher.is_published_version:
            btn = buttons.get('delete')
            if obj.translations.all().count() > 1:
                btn['url'] = obj.publisher.admin_urls.delete_translation()
                btn['label'] = '{} ({})'.format(
                    btn['label'],
                    language_code.upper(),
                )
        return buttons

    def delete_translation(self, request, object_id, language_code):
        root_model = self.model._parler_meta.root_model
        try:
            translation = root_model.objects.get(master_id=unquote(object_id), language_code=language_code)
        except root_model.DoesNotExist:
            raise Http404
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
            return (
                super(PublisherParlerAdminMixin, self)
                .delete_translation(request, object_id, language_code)
            )
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

    def get_change_form_base_template(self):
        """
        Determine what the actual `change_form_template` should be.
        """
        from parler.admin import _lazy_select_template_name
        opts = self.model._meta
        app_label = opts.app_label
        return _lazy_select_template_name((
            "admin/{0}/{1}/publisher_hange_form.html".format(app_label, opts.object_name.lower()),
            "admin/{0}/publisher_change_form.html".format(app_label),
            "admin/publisher_change_form.html",
            "admin/djangocms_publisher/publisher_change_form.html",
        ))

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
