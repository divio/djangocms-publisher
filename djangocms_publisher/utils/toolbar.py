# -*- coding: utf-8 -*-
import json

from cms.constants import RIGHT
from cms.toolbar.items import Button, ButtonList
from django.utils.encoding import force_text


class AjaxButton(Button):
    # FIXME: The cms ought to provide this. Make a PR.
    template = "admin/djangocms_publisher/cms-toolbar-items/button_ajax.html"

    def __init__(self, name, action, csrf_token, data=None, active=False,
                 disabled=False, extra_classes=None,
                 question=None, on_success=None):
        super(AjaxButton, self).__init__(
            name=name,
            url=action,
            active=active,
            disabled=disabled,
            extra_classes=extra_classes,
        )
        self.name = name
        self.action = action
        self.active = active
        self.disabled = disabled
        self.csrf_token = csrf_token
        self.data = data or {}
        self.extra_classes = extra_classes or []
        self.question = question
        self.on_success = on_success

    def __repr__(self):
        return '<AjaxButton:%s>' % force_text(self.name)

    def get_context(self):
        data = {}
        data.update(self.data)
        data['csrfmiddlewaretoken'] = self.csrf_token
        data = json.dumps(data)
        return {
            'action': self.action,
            'name': self.name,
            'active': self.active,
            'disabled': self.disabled,
            'extra_classes': self.extra_classes,
            'data': data,
            'question': self.question,
            'on_success': self.on_success
        }


def add_ajax_button(
    toolbar,
    **kwargs
):
    extra_wrapper_classes = kwargs.pop('extra_wrapper_classes', None)
    side = kwargs.pop('side', RIGHT)
    position = kwargs.pop('position', None)
    kwargs['csrf_token'] = toolbar.csrf_token
    buttonlist = ButtonList(extra_classes=extra_wrapper_classes, side=side)
    button = AjaxButton(**kwargs)
    buttonlist.add_item(button)
    toolbar.add_item(buttonlist, position=position)
    return buttonlist
