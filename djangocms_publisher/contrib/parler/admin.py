# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.utils.encoding import force_text
from ...admin import PublisherAdminMixinBase, get_all_button_defaults
from . import utils


class PublisherParlerAdminMixin(PublisherAdminMixinBase):
    delete_confirmation_template = 'admin/djangocms_publisher/contrib/parler/translation_delete_request_confirmation.html'

    @property
    def change_form_template(self):
        """
        Dynamic property to support transition to regular models.

        This automatically picks ``admin/parler/change_form.html`` when the admin uses a translatable model.
        """
        if self._has_translatable_model():
            # While this breaks the admin template name detection,
            # the get_change_form_base_template() makes sure it inherits from your template.
            return 'admin/djangocms_publisher/contrib/parler/parler_publisher_change_form.html'
        else:
            return None # get default admin selection

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
        # HACK to keep the current language when navigating between draft and
        # published.
        buttons = (
            super(PublisherParlerAdminMixin, self)
            .publisher_get_buttons(request, obj)
        )
        language_code = request.GET.get('language_code')
        if not language_code:
            language_code = getattr(obj, 'language_code', None)
        if not language_code:
            return buttons

        for name, button in buttons.items():
            # Add the language to the button labels for clarity
            if name in (
                    'publish',
                    'show_live',
                    'create_draft',
                    'discard_draft',
                    'edit',
                    'edit_draft',
            ):
                label = button.get('label')
                if label:
                    button['label'] = '{} ({})'.format(
                        label,
                        language_code.upper(),
                    )
            # Add the language to the url, so we don't loose that context
            url = button.get('url', None)
            if not url or '?language=' in url:
                continue
            button['url'] = url + '?language={}'.format(language_code)
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
        # This means it is a draft or published object that we can request
        # deletion for.
        if not self.has_change_permission(request, translation.master):
            raise PermissionDenied
        if request.method == 'POST':
            published_translation = translation.publisher.request_deletion()
            return HttpResponseRedirect(
                self.publisher_get_detail_admin_url(published_translation)
            )
        opts = self.model._meta
        object_name = _('{0} Translation').format(
            force_text(opts.verbose_name),
        )
        context = {
            "title": _("Are you sure?"),
            "object_name": object_name,
            "object": translation,
            "opts": opts,
            "app_label": opts.app_label,
        }

        return render(request, self.delete_confirmation_template or [
            "admin/%s/%s/parler_delete_request_confirmation.html" % (opts.app_label, opts.object_name.lower()),
            "admin/%s/parler_delete_request_confirmation.html" % opts.app_label,
            "admin/parler_delete_request_confirmation.html"
        ], context)

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
    publisher_translation_states.short_description = '<strong>EN</strong> DE FR'

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
