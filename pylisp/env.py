# -*- coding: utf-8 -*-
import builtins


class PythonBuiltins(object):

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
