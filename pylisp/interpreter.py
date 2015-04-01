# -*- coding: utf-8 -*-
import copy

import logging
from functools import reduce, partial
from contextlib import contextmanager
from collections import ChainMap
import operator
from . import types 
from .env import PythonBuiltins
from .utils import MethodDict
from .types import Procedure, Continuation

_log = logging.getLogger(__name__)


def special(fun):
    setattr(fun, '_special', True)
    return fun


class Interpreter(object):

    _log = _log.getChild('Evaluator')
    lookup = MethodDict()

    def __init__(self, env=None):
        # Separate env stack is required, since special methods have
        # no continuation
        self._envs = env or ChainMap(
            {
                'nil': None,
                '+': lambda *args: sum(args),
                '-': lambda *args: reduce(operator.sub, args),
                '*': lambda *args: reduce(operator.mul, args),
                '%': operator.mod,
                '=': operator.eq,
                '!=': operator.ne,
                '<': operator.lt,
                '>': operator.gt,
                '<=': operator.le,
                '>=': operator.ge,
                '.': self.getattr_,
                '.=': self.setattr_,
                'eq?': operator.is_,
                'set!': self.setbang,
                'set-car!': self.setcarbang,
                'set-cdr!': self.setcdrbang,
                'if': self.if_,
                'define': self.define,
                'eval': self.eval,
                'quote': self.quote,
                'lambda': self.lambda_,
                'list': self.list,
                'car': self.car,
                'cdr': self.cdr,
                'let': self.let,
                'cons': self.cons,
                'begin': self.begin,
                'call/cc': self.call_cc,
            },
            PythonBuiltins()
        )
        self._nil = None
        self._currcontinuation = None

    def eval(self, obj):
        self._log.debug('eval: %s', obj)
        evaluator = self.lookup.get(type(obj))

        if evaluator:
            return evaluator(self, obj)

        return obj

    @lookup.annotate(types.Cons)
    def expr(self, cons):
        values = (c.car for c in cons)
        fun = self.eval(next(values))

        if isinstance(fun, Procedure):
            fun = partial(self._call_procedure, fun)

        elif isinstance(fun, Continuation):
            return self._run_continuation(copy.copy(fun))

        elif getattr(fun, '_special', False):
            return fun(*values)

        return fun(*map(self.eval, values))

    @lookup.annotate(types.Symbol)
    def symbol(self, symbol):
        return self._envs[symbol.name]

    @special
    def begin(self, *exprs):
        value = None

        for expr in exprs:
            value = self.eval(expr)

        return value

    @special
    def setbang(self, symbol, value):
        if not isinstance(symbol, types.Symbol):
            raise TypeError("{!r} is not a symbol".format(symbol))

        for env in self._envs.maps:
            if symbol.name in env:
                env[symbol.name] = self.eval(value)
                return

        raise NameError("'{}' not defined".format(symbol))

    @special
    def if_(self, pred, then, else_=None):
        if self.eval(pred):
            return self.eval(then)

        else:
            return self.eval(else_)

    @special
    def define(self, symbol, *value):
        if isinstance(symbol, types.Cons):
            args = symbol.cdr
            symbol = symbol.car
            value = self.lambda_(args, *value)
            value.name = symbol

        else:
            value = self.eval(value[0])

        self._envs[symbol.name] = value
        self._log.debug('define: %s', self._envs)

    @special
    def quote(self, value):
        return value

    @special
    def lambda_(self, args, *body):
        if args is self._nil:
            args = ()

        else:
            args = tuple(c.car.name for c in args)

        return Procedure(None, args, body, self._envs)

    @special
    def call_cc(self, fun):
        self.expr(self.cons(fun, self.cons(self._currcontinuation, None)))

    @special
    def jump(self, proc, *args):
        # Build a new calling environment
        env = self._envs.new_child(
            proc.env
        ).new_child(
            dict(zip(proc.args, map(self.eval, args)))
        )
        # Return a new continuation (reset to start of proc)
        return Continuation(env, proc.body)

    def list(self, *args):
        cons = head = types.Cons(args[0])

        for arg in args[1:]:
            cons.cdr = types.Cons(arg)
            cons = cons.cdr

        return head

    def car(self, cons):
        return cons.car

    @special
    def setcarbang(self, symbol, value):
        self._envs[symbol.name].car = self.eval(value)

    def cdr(self, cons):
        return cons.cdr

    @special
    def setcdrbang(self, symbol, value):
        self._envs[symbol.name].cdr = self.eval(value)

    @special
    def let(self, defs, *body):
        env = self._envs.new_child()

        with self.over(env):
            for d in defs:
                symbol = d.car.car
                value = d.car.cdr.car
                env[symbol.name] = self.eval(value)

            return self._run_continuation(Continuation(env, body))

    def cons(self, car, cdr):
        return types.Cons(car, cdr)

    @special
    def getattr_(self, obj, attr, *default):
        if default:
            default = tuple(self.eval(d) for d in default)

        return getattr(self.eval(obj), attr.name, *default)

    @special
    def setattr_(self, obj, attr, value):
        setattr(self.eval(obj), attr.name, self.eval(value))

    @contextmanager
    def over(self, env):
        _envs = self._envs
        self._envs = env

        try:
            yield

        finally:
            self._envs = _envs

    def _call_procedure(self, proc, *args):
        if len(proc.args) != len(args):
            raise TypeError('expected {} arguments, got {}'.format(
                len(proc.args), len(args)))

        env = self._envs.new_child(
            proc.env
        ).new_child(
            dict(zip(proc.args, args))
        )

        continuation = Continuation(env, proc.body)
        return self._run_continuation(continuation)

    def _run_continuation(self, continuation):
        value = continuation

        while isinstance(value, Continuation):
            self._currcontinuation = cc = value

            with self.over(cc.env):
                pc = cc.next
                exprs = cc.exprs[pc:]

                for self._currcontinuation.next, expr in enumerate(exprs, pc + 1):
                    value = self.eval(expr)

        return value
