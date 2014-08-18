# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import builtins


class PythonBuiltins(object):

    @property
    def env(self):
        """
        It ends here
        """
        return None

    def __getitem__(self, symbol):
        attr = None
        if '.' in symbol:
            symbol, attr = symbol.split('.', 1)

        if hasattr(builtins, symbol):
            value = getattr(builtins, symbol)

            if attr:
                value = getattr(value, attr)

        else:
            raise NameError(symbol)

        return value

    def __contains__(self, symbol):
        return hasattr(builtins, symbol)

    def __repr__(self):
        return repr(builtins)


class Environment(object):

    def __init__(self, initial=None, env=None):
        self.values = initial or {}
        self.env = env

    def __getitem__(self, symbol):
        if symbol in self.values:
            return self.values[symbol]

        elif self.env:
            return self.env[symbol]

        raise NameError(symbol)

    def __setitem__(self, symbol, value):
        self.values[symbol] = value

    def update(self, *args, **kwgs):
        self.values.update(*args, **kwgs)

    def __contains__(self, symbol):
        return symbol in self.values

    def __repr__(self):
        return '<Environment at 0x{:x}, keys: {}, parent: {!r}>'.format(
            id(self), set(self.values.keys()), self.env)
