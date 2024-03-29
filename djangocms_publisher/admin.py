# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import OrderedDict
from copy import copy

from django.conf.urls import url
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.forms.widgets import Media
from django.http import HttpResponseRedirect, QueryDict
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from . import admin_views


class AdminUrls(object):
    def __init__(self, instance):
        self.instance = instance

    def get_url(self, name, get=None, args=None):
        if get is None:
            get = QueryDict()
        get = get.copy()
        obj = self.instance
        opts = self.instance._meta
        if args is None:
            args = (obj.pk,)
        url = reverse(
            'admin:{}_{}_{}'.format(
                opts.app_label,
                opts.model_name,
                name,
            ),
            args=args,
        )
        if get:
            url = '{}?{}'.format(url, get.urlencode())
        return url

    def get_action_url(self, action, **kwargs):
        return self.get_url(
            name='publisher_{}'.format(action),
            **kwargs
        )

    def create_draft(self, **kwargs):
        return self.get_action_url(action='create_draft', **kwargs)

    def discard_draft(self, **kwargs):
        return self.get_action_url(action='discard_draft', **kwargs)

    def publish(self, **kwargs):
        return self.get_action_url(action='publish', **kwargs)

    def change(self, **kwargs):
        return self.get_url('change', **kwargs)

    def request_deletion(self, **kwargs):
        return self.get_action_url(action='request_deletion', **kwargs)

    def discard_deletion_request(self, **kwargs):
        return self.get_action_url(action='discard_deletion_request', **kwargs)

    def delete(self, **kwargs):
        return self.get_url('delete', **kwargs)


class PublisherAdminMixinBase(object):
    @property
    def media(self):
        return super(PublisherAdminMixinBase, self).media + Media(
            css={
                'all': (
                    'djangocms_publisher/admin/djangocms_publisher.admin.css',
                ),
            },
        )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = (
            super(PublisherAdminMixinBase, self)
            .get_readonly_fields(request, obj=obj)
        )
        if not obj:
            return readonly_fields
        if obj.publisher_is_published_version:
            readonly_fields = set(readonly_fields)
            all_field_names = set([f.name for f in obj._meta.get_fields()])
            readonly_fields = readonly_fields | all_field_names
        return list(readonly_fields)

    def publisher_get_detail_or_changelist_url(self, obj, get=None):
        if not obj or obj and not obj.pk:  # No pk means the object was deleted
            return self.publisher_get_admin_changelist_url(obj, get=get)
        else:
            return self.publisher_get_detail_admin_url(obj, get=get)

    def publisher_get_detail_admin_url(self, obj, get=None):
        info = obj._meta.app_label, obj._meta.model_name
        return reverse('admin:{}_{}_change'.format(*info), args=(obj.pk,))

    def publisher_get_admin_changelist_url(self, obj=None, get=None):
        info = obj._meta.app_label, obj._meta.model_name
        return reverse('admin:{}_{}_changelist'.format(*info))

    def publisher_get_is_enabled(self, request, obj):
        # This allows subclasses to disable draft-live logic. Returning False
        # here will cause the "published" version in admin to be editable and
        # not show any of the special submit buttons for publishing.
        # Only override this if your app has a setting to disable publishing
        # alltogether.
        return True

    def has_delete_permission(self, request, obj=None):
        if obj and obj.pk and obj.publisher.is_published_version:
            if (
                obj.publisher.has_pending_deletion_request and
                self.has_publish_permission(request, obj)
            ):
                return True
            return False
        elif obj and obj.pk and obj.publisher.is_draft_version and obj.publisher.has_published_version:
            return False
        return (
            super(PublisherAdminMixinBase, self)
            .has_delete_permission(request, obj)
        )

    def has_publish_permission(self, request, obj):
        return self.has_change_permission(request, obj)

    def publisher_get_buttons(self, request, obj):
        is_enabled = self.publisher_get_is_enabled(request, obj)

        defaults = get_all_button_defaults()

        has_delete_permission = self.has_delete_permission(request, obj)
        has_change_permission = self.has_change_permission(request, obj)
        has_publish_permission = self.has_publish_permission(request, obj)
        add_mode = not bool(obj)
        buttons = {}
        if (
            not is_enabled and
            obj and obj.pk and
            obj.publisher_is_published_version and
            not obj.publisher_has_pending_changes
        ):
            # This is the case when we've disabled the whole draft/live
            # functionality. We just show the default django buttons.
            self._publisher_get_buttons_default(
                buttons=buttons,
                defaults=defaults,
                has_change_permission=has_change_permission,
                has_delete_permission=has_delete_permission,
            )
            return buttons

        if obj and obj.pk and obj.publisher.is_draft_version and has_change_permission:
            # Editing a draft version
            buttons['save'] = copy(defaults['save'])
            buttons['save_and_continue'] = copy(defaults['save_and_continue'])

        if (
            obj and obj.pk and obj.publisher.is_draft_version and
            not obj.publisher_is_published_version and
            has_delete_permission
        ):
            # A not published draft can be deleted the normal way
            buttons['delete'] = copy(defaults['delete'])

        if add_mode:
            self._publisher_get_buttons_default(
                buttons=buttons,
                defaults=defaults,
                has_change_permission=has_change_permission,
                has_delete_permission=has_delete_permission,
            )
        else:
            self._publisher_get_buttons_edit(
                buttons=buttons,
                obj=obj,
                defaults=defaults,
                has_publish_permission=has_publish_permission,
                has_delete_permission=has_delete_permission,
                request=request,
            )
        for button in buttons.values():
            if button.get('has_permission') is False and 'disabled_message' not in button:
                button['disabled_message'] = _('Permissions required')
        ordered_buttons = OrderedDict()
        for key in defaults.keys():
            if key not in buttons:
                continue
            ordered_buttons[key] = buttons.pop(key)
        for key, value in buttons.items():
            ordered_buttons[key] = value
        return ordered_buttons

    def _publisher_get_buttons_default(self, buttons, defaults, has_change_permission, has_delete_permission):
        if has_change_permission:
            buttons['save'] = copy(defaults['save'])
            buttons['save_and_continue'] = copy(defaults['save_and_continue'])
        if has_delete_permission:
            buttons['delete'] = copy(defaults['delete'])

    def _publisher_get_buttons_edit(self, buttons, defaults, obj, has_publish_permission, has_delete_permission, request, actions=None):
        action_urls = AdminUrls(obj)

        if actions is None:
            for action in obj.publisher.available_actions(request.user).values():
                action_name = action['name']
                buttons[action_name] = copy(defaults[action_name])
                btn = buttons[action_name]
                btn.update(action)
                if action_name == 'request_deletion':
                    # Show link to the request deletion view
                    btn['deletelink'] = True
                    btn['url'] = action_urls.request_deletion(get=request.GET)
                elif action_name == 'discard_requested_deletion':
                    btn['url'] = action_urls.discard_deletion_request(get=request.GET)
                elif action_name == 'discard_draft':
                    btn['deletelink'] = True
                    btn['url'] = action_urls.discard_draft(get=request.GET)
                elif action_name == 'create_draft':
                    btn['url'] = action_urls.create_draft(get=request.GET)
                else:
                    # Default is to use the action together with saving
                    btn['field_name'] = '_{}'.format(action_name)

        if not has_publish_permission:
            for action_name in ('publish', 'publish_deletion'):
                if action_name in buttons:
                    buttons[action_name]['has_permission'] = False

        # Additional links
        if obj.publisher.is_published_version and obj.publisher.has_pending_changes:
            # Add a link for editing an existing draft
            action_name = 'edit_draft'
            buttons[action_name] = copy(defaults[action_name])
            buttons[action_name]['url'] = self.publisher_get_detail_admin_url(obj.publisher.get_draft_version())
            buttons[action_name]['has_permission'] = True
        if obj.publisher.is_draft_version:
            # Add a link to go back to live
            action_name = 'show_live'
            buttons[action_name] = copy(defaults[action_name])
            if obj.publisher.has_published_version:
                buttons[action_name]['has_permission'] = True
                buttons[action_name]['url'] = self.publisher_get_detail_admin_url(obj.publisher.get_published_version())
            else:
                buttons[action_name]['has_permission'] = False
                buttons[action_name]['disabled_message'] = _('There is no published version yet.')
        elif obj.publisher.is_draft_version and not obj.publisher.has_published_version:
            # Add a link to go back to live
            action_name = 'show_live'
            buttons[action_name] = copy(defaults[action_name])
            buttons[action_name]['url'] = self.publisher_get_detail_admin_url(obj.publisher.get_published_version())
            buttons[action_name]['has_permission'] = True
        if obj.publisher.is_published_version and obj.publisher.has_pending_deletion_request:
            # We're going to take the shortcut and show the regular delete
            # view instead of the publish_deletion action, because that will
            # show the user the impact of the deletion.
            if has_publish_permission:
                buttons.pop('publish_deletion', None)
                buttons['delete'] = copy(defaults['delete'])

    def change_view(self, request, object_id, form_url='', extra_context=None):
        obj = self.get_object(request, object_id)
        is_enabled = self.publisher_get_is_enabled(request, obj)
        if is_enabled and obj and obj.publisher.is_published_version:
            # We don't allow editing the live version. Some apps will raise
            # validation errors if there are not fields in the POST
            # (django-parler). So if we're on the published view, everything is
            # is readonly anyway and there is no point in calling the whole
            # changeform logic. Just run the publisher actions and be done with
            # it.
            response = self.publisher_handle_actions(request, obj)
            if response:
                return response
        return super(PublisherAdminMixinBase, self).change_view(
            request, object_id, form_url=form_url, extra_context=extra_context)

    def response_change(self, request, obj):
        """
        On response_change we intentionally handle actions after the save has
        happened, so clicking on "publish" on a draft will save current changes
        in the form before publishing.
        """
        response = self.publisher_handle_actions(request, obj)
        if response:
            return response
        return super(PublisherAdminMixinBase, self).response_change(request, obj)

    def publisher_handle_actions(self, request, obj):
        """
        Used to handle the publisher workflow actions on response_change and
        change_view.
        """
        if request.POST and '_publish' in request.POST:
            if not self.has_publish_permission(request, obj):
                raise PermissionDenied
            published = obj.publisher.publish()
            return HttpResponseRedirect(self.publisher_get_detail_admin_url(published, get=request.GET))
        return None

    def publisher_get_action_urlpattern(self, view):
        opts = self.model._meta
        url_segment = view.action_name.replace('_', '-')
        url_name = '{0}_{1}_publisher_{2}'.format(
            opts.app_label,
            opts.model_name,
            view.action_name,
        )
        return url(
            r'^(?P<pk>.+)/' + url_segment + r'/$',
            self.admin_site.admin_view(view.as_view(admin=self)),
            name=url_name,
        )

    def publisher_get_urls(self):
        return [
            self.publisher_get_action_urlpattern(admin_views.RequestDeletion),
            self.publisher_get_action_urlpattern(admin_views.DiscardDeletionRequest),
            self.publisher_get_action_urlpattern(admin_views.CreateDraft),
            self.publisher_get_action_urlpattern(admin_views.DiscardDraft),
            self.publisher_get_action_urlpattern(admin_views.Publish),
        ]

    def get_urls(self):
        urlpatterns = super(PublisherAdminMixinBase, self).get_urls()
        return self.publisher_get_urls() + urlpatterns

    def publisher_get_status_field_context(self, obj):
        return {
            'state': obj.publisher.state,
        }

    def publisher_state(self, obj):
        context = self.publisher_get_status_field_context(obj)
        return render_to_string(
            'admin/djangocms_publisher/tools/status_indicator.html',
            context,
        )
    publisher_state.allow_tags = True
    publisher_state.short_description = ''


def get_all_button_defaults():
    defaults = OrderedDict()
    defaults['cancel'] = {'label': _('Cancel')}
    defaults['create_draft'] = {'label': _('Edit'), 'class': 'default'}
    defaults['edit_draft'] = {'label': _('Edit'), 'class': 'default'}
    defaults['show_live'] = {'label': _('View published version')}
    defaults['discard_draft'] = {'label': _('Discard changes'), 'class': 'danger'}
    defaults['publish'] = {'label': _('Publish'), 'class': 'default'}
    defaults['request_deletion'] = {'label': _('Request deletion'), 'deletelink_button': True}
    defaults['discard_requested_deletion'] = {'label': _('Discard deletion request')}
    defaults['publish_deletion'] = {'label': _('Delete'), 'class': 'danger', 'deletelink_button': True}

    # TODO: Support for "save as new" and "save and add another"
    defaults['save'] = {
        'label': _('Save'),
        'class': 'default',
        'field_name': '_save',
    }
    defaults['delete'] = {
        'deletelink': True,  # Special case in template
        'label': _('Delete'),
    }
    defaults['save_and_continue'] = {
        'label': _('Save and continue editing'),
        'field_name': '_continue',
    }
    for btn in defaults.values():
        btn['has_permission'] = True
    return defaults


class PublisherAdminMixin(PublisherAdminMixinBase):
    change_form_template = 'admin/djangocms_publisher/publisher_change_form.html'
