# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function


class MethodDict(dict):

    def annotate(self, identifier):
        def decorator(fun):
            self[identifier] = fun
            return fun

        return decorator
