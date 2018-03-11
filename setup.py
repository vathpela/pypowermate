#!/usr/bin/python3
#
# Copyright 2017 Peter Jones <pjones@redhat.com>
#
# Distributed under terms of the GPLv3 license.

"""setup module for powermate

"""

from setuptools import setup, find_packages

setup(
    name='powermate',
    version='0.0.2',
    description='Accept Input from a PowerMate',
    author='Peter Jones',
    author_email='pjones@redhat.com',
    license='GPL3+',
    packages=find_packages(exclude=['docs', 'tests']),
    entry_points={
    },
)

# -*- coding: utf-8 -*-
# vim:fenc=utf-8:tw=75
