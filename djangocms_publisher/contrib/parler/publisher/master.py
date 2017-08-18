# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from ....models import Publisher


class ParlerMasterPublisher(Publisher):
    """
    A publisher object for the parler master object. This is not directly
    accessible and only exists to be used by the language specific parler
    publisher.
    """
    pass
