#!/usr/bin/env python

import distutils.core

# Uploading to PyPI
# =================
# $ python setup.py register -r pypi
# $ python setup.py sdist upload -r pypi

version = '1.1'
distutils.core.setup(
        name='linersock',
        version=version,
        author='Kale Kundert and Alex Mitchell',
        packages=['linersock'],
        url='https://github.com/kxgames/linersock',
        download_url='https://github.com/kxgames/linersock/tarball/'+version,
        license='LICENSE.txt',
        description="A thin layer between you and your sockets that helps prevent chafing.",
        long_description=open('README.rst').read(),
        keywords=['nonblocking', 'socket', 'wrapper', 'library'])
