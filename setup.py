# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

import os

from setuptools import find_packages, setup

version = __import__('djangocms_publisher').__version__


def read(fname):
    # read the contents of a text file
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="djangocms-publisher",
    version=version,
    url='http://github.com/divio/djangocms-publisher',
    license='BSD',
    platforms=['OS Independent'],
    description="A toolkit to build draft/published support for 3rd party apps.",
    long_description=read('README.rst'),
    author='Divio AG',
    author_email='info@divio.ch',
    packages=find_packages(),
    install_requires=(
        'Django>=1.8,<1.10.999',  # Django is known to use rc versions
    ),
    include_package_data=True,
    zip_safe=False,
)
