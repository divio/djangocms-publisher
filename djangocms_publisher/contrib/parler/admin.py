# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from copy import copy

from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.utils.encoding import force_text
from ...admin import PublisherAdminMixinBase, get_all_button_defaults
from .utils import get_language_tabs


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
        return get_language_tabs(
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

    def publisher_get_admin_changelist_url(self, obj=None):
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
            .publisher_get_admin_changelist_url(master)
        )

    def publisher_get_detail_admin_url(self, obj, language_code=None):
        from parler.models import TranslatedFieldsModel
        if not language_code and isinstance(obj, TranslatedFieldsModel):
            # The url needs to use the id of the master object.
            language_code = obj.language_code
            obj = obj.master

        app_label = obj._meta.app_label
        model_name = obj._meta.model_name
        url = reverse(
            'admin:{}_{}_change'.format(app_label, model_name),
            args=(obj.pk,),
        )
        if language_code:
            url = url + '?language={}'.format(language_code)
        return url

    # def publisher_handle_actions(self, request, obj):
    #     """
    #     The Parler version of this uses the translated object instead of the
    #     main one for all the actions. The master object is always published
    #     together with any translation publishing as a side-effect.
    #     """
    #
    #     # FIXME: check permissions (edit)
    #     if request.POST and '_create_draft' in request.POST:
    #         if obj.publisher.is_published_version and obj.publisher.has_pending_changes:
    #             # There already is a draft. Just redirect to it.
    #             return HttpResponseRedirect(
    #                 self.publisher_get_detail_admin_url(
    #                     obj.publisher.get_draft_version()
    #                 )
    #             )
    #         draft = obj.publisher.create_draft()
    #         return HttpResponseRedirect(self.publisher_get_detail_admin_url(draft))
    #     elif request.POST and '_discard_draft' in request.POST:
    #         published_translation = obj.publisher.get_published_version()
    #         obj.publisher.discard_draft()
    #         return HttpResponseRedirect(
    #             self.publisher_get_detail_or_changelist_url(
    #                 published_translation.master,
    #                 language_code=published_translation.language_code,
    #             ),
    #         )
    #     elif request.POST and '_publish' in request.POST:
    #         # FIXME: check the user_can_publish() permission
    #         published_translation = obj.publisher.publish()
    #         return HttpResponseRedirect(
    #             self.publisher_get_detail_admin_url(
    #                 published_translation.master,
    #                 language_code=published_translation.language_code,
    #             ),
    #         )
    #     elif request.POST and '_request_deletion' in request.POST:
    #         published_translation = obj.publisher.request_deletion()
    #         return HttpResponseRedirect(
    #             self.publisher_get_detail_admin_url(
    #                 published_translation.master,
    #                 language_code=published_translation.language_code,
    #             )
    #         )
    #     elif request.POST and '_discard_requested_deletion' in request.POST:
    #         obj.publisher.discard_requested_deletion()
    #         return HttpResponseRedirect(self.publisher_get_detail_admin_url(obj))
    #     elif request.POST and '_publish_deletion' in request.POST:
    #         obj.publisher.publish_deletion()
    #         return HttpResponseRedirect(self.publisher_get_admin_changelist_url(obj))
    #     return None

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
    publisher_translation_states.short_description = ''

    def publisher_state_debug(self, obj):
        return render_to_string(
            'admin/djangocms_publisher/contrib/parler/debug/state_debug.html',
            context={'obj': obj},
        )
    publisher_state_debug.allow_tags = True
    publisher_state_debug.short_description = 'publisher state debug'
