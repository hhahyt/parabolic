# -*- coding: utf-8 -*-
#
import os
import codecs

from setuptools import setup, find_packages

# https://packaging.python.org/single_source_version/
base_dir = os.path.abspath(os.path.dirname(__file__))
about = {}
with open(os.path.join(base_dir, 'parabolic', '__about__.py'), 'rb') as f:
    # pylint: disable=exec-used
    exec(f.read(), about)


def read(fname):
    try:
        content = codecs.open(
            os.path.join(base_dir, fname),
            encoding='utf-8'
            ).read()
    except IOError:
        content = ''
    return content


setup(
    name='parabolic',
    version=about['__version__'],
    author=about['__author__'],
    author_email=about['__author_email__'],
    packages=find_packages(),
    description=(
        'Time-steppers for parabolic PDEs'
        ),
    long_description=read('README.rst'),
    url='https://github.com/nschloe/parabolic',
    download_url='https://github.com/nschloe/parabolic/releases',
    license=about['__license__'],
    platforms='any',
    install_requires=[
        'matplotlib',
        'numpy',
        'pipdate',
        ],
    classifiers=[
        about['__status__'],
        about['__license__'],
        'Intended Audience :: Science/Research',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering :: Mathematics'
        ],
    )
