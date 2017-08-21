# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth import get_permission_codename
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.utils.encoding import force_text
from django.utils.html import escape
from django.views.generic import View, DetailView
from django.utils.translation import ugettext_lazy as _
from djangocms_publisher.admin_views import AdminViewMixin, \
    AdminConfirmationViewMixin


# class ParlerAdminViewMixin(AdminViewMixin):
#     def get_object(self):
#         if 'language' in self.kwargs:
#             get = self.request.GET.copy()
#             get['language'] = self.kwargs['language']
#             self.request.GET = get
#         return self.admin.get_object(self.request, self.kwargs['pk'])
#
#
# class ParlerAdminConfirmationViewMixin(AdminConfirmationViewMixin):
#     template_name = 'admin/djangocms_publisher/confirmation.html'
#
#     def get_context_data(self, **kwargs):
#         context = super(ParlerAdminConfirmationViewMixin, self).get_context_data(**kwargs)
#         if context['object'].language_code:
#             context['object_name'] = '{} ({})'.format(
#                 context['object_name'],
#                 context['object'].language_code,
#             )
#         return context
#
#
# class CreateDraft(ParlerAdminViewMixin, ParlerAdminConfirmationViewMixin, DetailView):
#     action_name = 'create_draft'
#
#     def get_context_data(self, **kwargs):
#         context = super(CreateDraft, self).get_context_data(**kwargs)
#         context.update({
#             "action_title": _("Create Draft"),
#             "action_message": _(
#                 'Are you sure you want to create a draft for '
#                 'the {object_name} "{escaped_object}"?'
#             ).format(
#                 object_name=context['object_name'],
#                 escaped_object=escape(context['object']),
#             ),
#         })
#         return context
#
#     def post(self, request, *args, **kwargs):
#         obj = self.get_object()
#         draft_obj = obj.publisher.create_draft()
#         return HttpResponseRedirect(self.get_success_url(draft_obj))
