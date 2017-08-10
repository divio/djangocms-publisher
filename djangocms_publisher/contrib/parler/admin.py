# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from parler.utils.compat import transaction_atomic

from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.template.loader import render_to_string
from .admin import PublisherAdminMixinBase


class PublisherParlerAdminMixin(PublisherAdminMixinBase):

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

        if obj.publisher_is_published_version:
            draft_translations = obj.publisher_has_pending_changes
            published_translations = obj.translations.filter(language_code__in=languages)

            if obj.publisher_has_pending_changes:
                draft_translations = obj.publisher_draft_version.translations.filter(language_code__in=languages)
            else:
                draft_translations = published_translations.none()
        else:
            draft_translations = obj.translations.filter(language_code__in=languages)

            if obj.publisher_has_published_version:
                published_translations = obj.publisher_published_version.translations.filter(language_code__in=languages)
            else:
                published_translations = draft_translations.none()

        draft_translations_by_language = {trans.language_code: trans for trans in draft_translations}
        published_translations_by_language = {trans.language_code: trans for trans in published_translations}

        for pos, tab in enumerate(tabs):
            language = tab[2]
            draft_translation = draft_translations_by_language.get(language)
            published_translation = published_translations_by_language.get(language)

            if published_translation and obj.publisher_is_draft_version:
                # change link to point to published version of language
                url_name = 'admin:%s_%s_%s' % (self.opts.app_label, self.opts.model_name, 'change')
                tabs[pos] = list(tabs[pos])
                tabs[pos][0] = reverse(url_name, args=[published_translation.master_id]) + tabs[pos][0]
            elif not published_translation and obj.publisher_is_published_version:
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
        for button in buttons.values():
            if 'language' in request.GET and 'url' in button:
                button['url'] = button['url'] + '?language={}'.format(request.GET['language'])
        return buttons

    @transaction_atomic
    def delete_translation(self, request, object_id, language_code):
        root_model = self.model._parler_meta.root_model
        try:
            translation = root_model.objects.get(master_id=unquote(object_id), language_code=language_code)
        except root_model.DoesNotExist:
            raise Http404

        is_published_version_and_deletion_already_requested = (
            translation.translation_publisher.is_published_version and
            translation.translation_publisher.has_pending_deletion_request
        )
        is_draft_version_and_no_published_version_exists = (
            translation.translation_publisher.is_draft_version and
            not translation.translation_publisher.has_published_version
        )
        if (
            is_published_version_and_deletion_already_requested or
            is_draft_version_and_no_published_version_exists
        ):
            # In this case we show the normal delete view because we'll actually
            # want to delete the object for real.
            if not self.has_publish_permission(request, translation):
                raise PermissionDenied
            return (
                super(PublisherParlerAdminMixin, self)
                .delete_translation(request, object_id, language_code)
            )
        # This means it is a draft or published object that we can request
        # deletion for.
        if request.method == 'POST':
            published_translation = translation.translation_publisher.request_deletion()
            return HttpResponseRedirect(
                self.publisher_get_admin_changelist_url(published_translation)
            )
        # FIXME: We need to change the message on this view to reflect that it
        #        is a deletion request, not the actual deletion.
        return (
            super(PublisherParlerAdminMixin, self)
            .delete_translation(request, object_id, language_code)
        )

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

    # def publisher_get_detail_admin_url(self, obj):
    #     app_label = obj._meta.app_label
    #     model_name = obj._meta.model_name
    #
    #     from parler.models import TranslatedFieldsModel
    #     if isinstance(obj, TranslatedFieldsModel):
    #         # The url needs to use the id of the master object.
    #         master = obj.master
    #         language_code = obj.language_code
    #         model_name = master._meta.model_name
    #     else:
    #         master = obj
    #         language_code = getattr(obj, 'language_code', None)
    #     print model_name, master, language_code
    #     url = reverse(
    #         'admin:{}_{}_change'.format(app_label, model_name),
    #         args=(master.pk,),
    #     )
    #     if language_code:
    #         url = url + '?language={}'.format(language_code)
    #     print url
    #     return url

    def publisher_handle_actions(self, request, obj):
        """
        The Parler version of this uses the translated object instead of the
        main one for all the actions. The master object is always published
        together with any translation publishing as a side-effect.
        """
        assert obj.publisher_is_parler_master_model
        # This is the parler master model. Switch to the translation model
        # so we are working with the right object.
        try:
            obj = obj.translations.get(language_code=obj.language_code)
        except obj.translations.model.DoesNotExist:
            return None

        # FIXME: check permissions (edit)
        if request.POST and '_create_draft' in request.POST:
            if obj.translation_publisher.is_published_version and obj.translation_publisher.has_pending_changes:
                # There already is a draft. Just redirect to it.
                return HttpResponseRedirect(
                    self.publisher_get_detail_admin_url(
                        obj.translation_publisher.get_draft_version()
                    )
                )
            draft = obj.translation_publisher.create_draft()
            return HttpResponseRedirect(self.publisher_get_detail_admin_url(draft))
        elif request.POST and '_discard_draft' in request.POST:
            published = obj.translation_publisher.get_published_version()
            obj.translation_publisher.discard_draft()
            return HttpResponseRedirect(self.publisher_get_detail_or_changelist_url(published))
        elif request.POST and '_publish' in request.POST:
            # FIXME: check the user_can_publish() permission
            published = obj.translation_publisher.publish()
            return HttpResponseRedirect(self.publisher_get_detail_admin_url(published))
        elif request.POST and '_request_deletion' in request.POST:
            published = obj.translation_publisher.request_deletion()
            return HttpResponseRedirect(self.publisher_get_detail_admin_url(published))
        elif request.POST and '_discard_requested_deletion' in request.POST:
            obj.translation_publisher.discard_requested_deletion()
            return HttpResponseRedirect(self.publisher_get_detail_admin_url(obj))
        elif request.POST and '_publish_deletion' in request.POST:
            obj.translation_publisher.publish_deletion()
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
