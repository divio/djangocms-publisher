# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth import get_permission_codename
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.utils.encoding import force_text
from django.utils.html import escape
from django.views.generic import View, DetailView
from django.utils.translation import ugettext_lazy as _


class AdminViewMixin(object):
    # FIXME: permission checks
    admin = None
    opts = None

    def __init__(self, *args, **kwargs):
        super(AdminViewMixin, self).__init__(*args, **kwargs)
        self.opts = self.admin.model._meta

    def get_queryset(self):
        return self.admin.get_queryset(self.request)

    def get_object(self):
        return self.admin.get_object(self.request, self.kwargs['pk'])

    def has_permission(self):
        return self.request.user.has_perm(
            '{}.{}'.format(
                self.opts.app_label,
                get_permission_codename('change', self.opts),
            )
        )

    def get_context_data(self, **kwargs):
        context = super(AdminViewMixin, self).get_context_data(**kwargs)
        context.update({
            'admin_site': self.admin.admin_site.name,
            'title': 'Process: ' + force_text(self.get_object()),
            'opts': self.opts,
            'app_label': self.opts.app_label,
            'has_change_permission': self.has_permission(),
        })
        return context

    def get_success_url(self, obj):
        redirect = self.request.POST.get(
            'redirect',
            self.request.GET.get('redirect', 'admin')
        )
        if redirect == 'onsite':
            # Dirty workaround so we don't have to subclass all these views in
            # contrib.parler.
            language = self.request.GET.get('language', None)
            try:
                return obj.get_absolute_url(language=language)
            except TypeError:
                return obj.get_absolute_url()
        return obj.publisher.admin_urls.change(get=self.request.GET)


class AdminConfirmationViewMixin(AdminViewMixin):
    template_name = 'admin/djangocms_publisher/confirmation.html'

    def get_context_data(self, **kwargs):
        context = super(AdminConfirmationViewMixin, self).get_context_data(**kwargs)
        opts = self.admin.model._meta
        context.update({
            "title": _("Are you sure?"),
            "object_name": force_text(opts.verbose_name),
            "object": self.get_object(),
            "action_title": None,
            "action_message": _("Are you sure?"),
        })
        return context


class RequestDeletion(AdminConfirmationViewMixin, DetailView):
    action_name = 'request_deletion'

    def get_context_data(self, **kwargs):
        context = super(RequestDeletion, self).get_context_data(**kwargs)
        context.update({
            "title": _("Are you sure?"),
            "action_title": _("Request deletion"),
            "action_message": _(
                'Are you sure you want to request deletion for '
                'the {object_name} "{escaped_object}"?'
            ).format(
                object_name=context['object_name'],
                escaped_object=escape(context['object']),
            ),
        })
        return context

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.publisher.request_deletion()
        return HttpResponseRedirect(self.get_success_url(obj))


class DiscardDeletionRequest(AdminConfirmationViewMixin, DetailView):
    action_name = 'discard_deletion_request'

    def get_context_data(self, **kwargs):
        context = super(DiscardDeletionRequest, self).get_context_data(**kwargs)
        context.update({
            "action_title": _("Discard Deletion request"),
            "action_message": _(
                'Are you sure you want to discard the deletion request for '
                'the {object_name} "{escaped_object}"?'
            ).format(
                object_name=context['object_name'],
                escaped_object=escape(context['object']),
            ),
        })
        return context

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.publisher.discard_deletion_request()
        return HttpResponseRedirect(self.get_success_url(obj))


class CreateDraft(AdminConfirmationViewMixin, DetailView):
    action_name = 'create_draft'

    def get_context_data(self, **kwargs):
        context = super(CreateDraft, self).get_context_data(**kwargs)
        context.update({
            "action_title": _("Create Draft"),
            "action_message": _(
                'Are you sure you want to create a draft for '
                'the {object_name} "{escaped_object}"?'
            ).format(
                object_name=context['object_name'],
                escaped_object=escape(context['object']),
            ),
        })
        return context

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        draft_obj = obj.publisher.create_draft()
        return HttpResponseRedirect(self.get_success_url(draft_obj))


class DiscardDraft(AdminConfirmationViewMixin, DetailView):
    action_name = 'discard_draft'

    def get_context_data(self, **kwargs):
        context = super(DiscardDraft, self).get_context_data(**kwargs)
        context.update({
            "action_title": _("Discard draft changes"),
            "action_message": _(
                'Are you sure you want to discard draft changes for '
                'the {object_name} "{escaped_object}"?'
            ).format(
                object_name=context['object_name'],
                escaped_object=escape(context['object']),
            ),
        })
        return context

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        published_obj = obj.publisher.get_published_version()
        obj.publisher.discard_draft()
        return HttpResponseRedirect(self.get_success_url(published_obj))


class Publish(AdminConfirmationViewMixin, DetailView):
    action_name = 'publish'

    def get_context_data(self, **kwargs):
        context = super(Publish, self).get_context_data(**kwargs)
        context.update({
            "action_title": _("Publish"),
            "action_message": _(
                'Are you sure you want to publish changes for '
                'the {object_name} "{escaped_object}"?'
            ).format(
                object_name=context['object_name'],
                escaped_object=escape(context['object']),
            ),
        })
        return context

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        published_obj = obj.publisher.publish()
        return HttpResponseRedirect(self.get_success_url(published_obj))
