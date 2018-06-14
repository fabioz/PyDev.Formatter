#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

import os

from setuptools import find_packages, setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = ['Click>=6.0', ]

setup_requirements = [
#     'pytest-runner',
]

test_requirements = [
#     'pytest',
]


base = os.path.dirname(os.path.join(__file__))


data_files = [
    os.path.join(base, 'pydevf/pydev_formatter.jar'),
    os.path.join(base, 'pydevf/pydev_formatter_lib/org.eclipse.equinox.common_3.10.0.v20180412-1130.jar'),
    os.path.join(base, 'pydevf/pydev_formatter_lib/org.eclipse.text_3.6.300.v20180430-1330.jar'),
]

for f in data_files:
    assert os.path.exists(f), 'Expected: %s to exist.' % (f,)


setup(
    author="Fabio Zadrozny",
    author_email='fabiofz@gmail.com',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Eclipse Public License 2.0 (EPL-2.0)',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    description="PyDev Code Formatter",
    entry_points={
        'console_scripts': [
            'pydevf=pydevf:main',
        ],
    },
    install_requires=requirements,
    license="EPL (Eclipse Public License)",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords=['pydevf', 'pydev formatter', 'pydev'],
    name='pydevf',
    packages=find_packages(include=['pydevf']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/fabioz/pydevf',
    version='0.1.3',
    zip_safe=False,
    data_files=data_files,
)
