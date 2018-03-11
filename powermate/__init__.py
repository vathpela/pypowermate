#!/usr/bin/python3
#
# Copyright 2018 Peter Jones <pjones@redhat.com>
#
# Distributed under terms of the GPLv3 license.

"""
Library to use a Griffen PowerMate through select.
"""

from .powermate import PowerMateDispatcher, PowerMate, UdevMonitor

__all__ = ['PowerMateDispatcher', 'PowerMate', 'UdevMonitor']

# -*- coding: utf-8 -*-
# vim:fenc=utf-8:tw=75
