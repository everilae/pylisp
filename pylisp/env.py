# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import builtins


class PythonBuiltins(object):

    @property
    def parent(self):
        """
        It ends here
        """
        return None

    def __getitem__(self, name):
        attr = None
        if '.' in name:
            name, attr = name.split('.', 1)

        if hasattr(builtins, name):
            value = getattr(builtins, name)

            if attr:
                value = getattr(value, attr)

        else:
            raise NameError(name)

        return value

    def __contains__(self, name):
        return hasattr(builtins, name)

    def __repr__(self):
        return repr(builtins)


class Environment(object):

    def __init__(self, initial=None, parent=None):
        self.values = initial or {}
        self.parent = parent

    def __getitem__(self, name):
        if name in self.values:
            return self.values[name]

        elif self.parent:
            return self.parent[name]

        raise NameError(name)

    def __setitem__(self, name, value):
        self.values[name] = value

    def update(self, *args, **kwgs):
        self.values.update(*args, **kwgs)

    def __contains__(self, name):
        return name in self.values or self.parent and name in self.parent

    def __repr__(self):
        return '<Environment {!r} at 0x{:x}, parent: {!r}>'.format(
            self.values, id(self), self.parent)
