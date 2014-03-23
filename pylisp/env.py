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

    def __getitem__(self, symbol):
        name = symbol.name
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

    def __contains__(self, symbol):
        name = symbol.name
        return hasattr(builtins, name)

    def __repr__(self):
        return repr(builtins)


class Environment(object):

    def __init__(self, initial=None, parent=None):
        self.values = initial or {}
        self.parent = parent

    def __getitem__(self, symbol):
        if symbol in self.values:
            return self.values[symbol]

        elif self.parent:
            return self.parent[symbol]

        raise NameError(symbol)

    def __setitem__(self, symbol, value):
        self.values[symbol] = value

    def update(self, *args, **kwgs):
        self.values.update(*args, **kwgs)

    def __contains__(self, symbol):
        return symbol in self.values

    def __repr__(self):
        return '<Environment at 0x{:x}, keys: {}, parent: {!r}>'.format(
            id(self), set(self.values.keys()), self.parent)
