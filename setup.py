#!/usr/bin/env python
import os

try:
    from setuptools import setup, Extension
except ImportError:
    from distutils.core import setup, Extension

from litman.version import get_version


def read(fname):
    try:
        return open(os.path.join(os.path.dirname(__file__), fname)).read()
    except:
        return ''


setup(
    name='litman',
    version=get_version(),
    description='Literature manager',
    long_description=read('readme.rst'),
    author='Mark Muetzelfeldt',
    author_email='m.muetzelfeldt@pgr.reading.ac.uk',
    maintainer='Mark Muetzelfeldt',
    maintainer_email='m.muetzelfeldt@pgr.reading.ac.uk',
    packages=['litman',
              'litman.cmds',
              ],
              # 'litman.tests'],
    scripts=[
        'bin/litman',
        'bin/litman_web',
        ],
    # fstrings support needed.
    python_requires='>=3.6',
    install_requires=[
        'pybtex',
        'configparser',
        'requests',
        ],
    # Install with e.g. `pip install -e .[experimental]`
    extras_require= {
        'experimental': ['flask', 'graphviz'],
        },
    package_data={ },
    url='https://github.com/markmuetz/litman',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.6',
        ],
    keywords=[''],
    )
