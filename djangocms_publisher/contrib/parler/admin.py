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


class PublisherParlerAdminMixin(PublisherAdminMixinBase):
    delete_confirmation_template = 'admin/djangocms_publisher/contrib/parler/translation_delete_request_confirmation.html'

    def get_language_tabs(self, request, obj, available_languages, css_class=None):
        """
        Determine the language tabs to show.
        """
        tabs = super(PublisherParlerAdminMixin, self).get_language_tabs(
            request,
            obj=obj,
            available_languages=available_languages,
            css_class=css_class,
        )
        if not obj or obj and not obj.pk:
            # Is this ok to do? (The "add" view)
            return tabs

        languages = [tab[2] for tab in tabs]

        if obj.publisher.is_published_version:
            # draft_translations = obj.publisher.has_pending_changes
            published_translations = obj.translations.filter(language_code__in=languages)

            if obj.publisher.has_pending_changes:
                draft_translations = obj.publisher.get_draft_version().translations.filter(language_code__in=languages)
            else:
                draft_translations = published_translations.none()
        else:
            draft_translations = obj.translations.filter(language_code__in=languages)

            if obj.publisher.has_published_version:
                published_translations = obj.publisher.get_published_version().translations.filter(language_code__in=languages)
            else:
                published_translations = draft_translations.none()

        draft_translations_by_language = {trans.language_code: trans for trans in draft_translations}
        published_translations_by_language = {trans.language_code: trans for trans in published_translations}

        for pos, tab in enumerate(tabs):
            language = tab[2]
            draft_translation = draft_translations_by_language.get(language)
            published_translation = published_translations_by_language.get(language)

            if published_translation and obj.publisher.is_draft_version:
                # change link to point to published version of language
                url_name = 'admin:%s_%s_%s' % (self.opts.app_label, self.opts.model_name, 'change')
                tabs[pos] = list(tabs[pos])
                tabs[pos][0] = reverse(url_name, args=[published_translation.master_id]) + tabs[pos][0]
            elif not published_translation and obj.publisher.is_published_version:
                # User is on published version of master object
                # but there's no published version for tab language
                if draft_translation:
                    # Link directly to the draft version
                    url_name = 'admin:%s_%s_%s' % (self.opts.app_label, self.opts.model_name, 'change')
                    tabs[pos] = list(tabs[pos])
                    tabs[pos][0] = reverse(url_name, args=[draft_translation.master_id]) + tabs[pos][0]
                else:
                    # Link to custom endpoint that creates draft version
                    # of master and/or draft version of language
                    tabs[pos] = list(tabs[pos])
                    tabs[pos][0] = tabs[pos][0] + '&CUSTOM_ENDPOINT_TO_CREATE_A_DRAFT_VERSION=True'
        return tabs

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
        translation = obj.translations.get(language_code=language_code)
        defaults = get_all_button_defaults()
        if (
            translation.publisher.is_published_version and
            translation.publisher.has_pending_changes
        ):
            # In this case we need to put the correct action here for linking
            # to the draft instead of creating it.
            buttons.pop('create_draft', None)
            action_name = 'edit_draft'
            buttons[action_name] = copy(defaults[action_name])
            buttons[action_name]['url'] = self.publisher_get_detail_admin_url(
                obj.publisher_draft_version,
                language_code=language_code,
            )
            buttons[action_name]['has_permission'] = True
        elif (
            translation.publisher.is_published_version and
            not translation.publisher.has_pending_changes
        ):
            # In this case we need to put the correct action here for linking
            # to the draft instead of creating it.
            buttons.pop('edit_draft', None)
            action_name = 'create_draft'
            buttons[action_name] = copy(defaults[action_name])
            buttons[action_name].update(
                translation.publisher.available_actions(request.user)[action_name]
            )
            buttons[action_name]['field_name'] = '_{}'.format(action_name)

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
            # Add the language to the url, so we don't use that context
            url = button.get('url', None)
            if not url or '?language=' in url:
                print 'skipping', url, button
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

    def publisher_handle_actions(self, request, obj):
        """
        The Parler version of this uses the translated object instead of the
        main one for all the actions. The master object is always published
        together with any translation publishing as a side-effect.
        """
        # assert obj.publisher_is_parler_master_model
        # # This is the parler master model. Switch to the translation model
        # # so we are working with the right object.
        # try:
        #     obj = obj.translations.get(language_code=obj.language_code)
        # except obj.translations.model.DoesNotExist:
        #     return None

        # FIXME: check permissions (edit)
        if request.POST and '_create_draft' in request.POST:
            if obj.publisher.is_published_version and obj.publisher.has_pending_changes:
                # There already is a draft. Just redirect to it.
                return HttpResponseRedirect(
                    self.publisher_get_detail_admin_url(
                        obj.publisher.get_draft_version()
                    )
                )
            draft = obj.publisher.create_draft()
            return HttpResponseRedirect(self.publisher_get_detail_admin_url(draft))
        elif request.POST and '_discard_draft' in request.POST:
            published_translation = obj.publisher.get_published_version()
            obj.publisher.discard_draft()
            return HttpResponseRedirect(
                self.publisher_get_detail_or_changelist_url(
                    published_translation.master,
                    language_code=published_translation.language_code,
                ),
            )
        elif request.POST and '_publish' in request.POST:
            # FIXME: check the user_can_publish() permission
            published_translation = obj.publisher.publish()
            return HttpResponseRedirect(
                self.publisher_get_detail_admin_url(
                    published_translation.master,
                    language_code=published_translation.language_code,
                ),
            )
        elif request.POST and '_request_deletion' in request.POST:
            published_translation = obj.publisher.request_deletion()
            return HttpResponseRedirect(
                self.publisher_get_detail_admin_url(
                    published_translation.master,
                    language_code=published_translation.language_code,
                )
            )
        elif request.POST and '_discard_requested_deletion' in request.POST:
            obj.publisher.discard_requested_deletion()
            return HttpResponseRedirect(self.publisher_get_detail_admin_url(obj))
        elif request.POST and '_publish_deletion' in request.POST:
            obj.publisher.publish_deletion()
            return HttpResponseRedirect(self.publisher_get_admin_changelist_url(obj))
        return None

    def publisher_status_parler(self, obj):
        context = self.publisher_get_status_field_context(obj)
        return render_to_string(
            'admin/djangocms_publisher/tools/status_label_parler_all.html',
            context,
        )
    publisher_status_parler.allow_tags = True
    publisher_status_parler.short_description = ''
