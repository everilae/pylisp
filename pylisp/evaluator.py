# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import logging
from functools import reduce
from contextlib import contextmanager
import operator
from . import types 
from .env import Environment, PythonBuiltins
from pylisp.exceptions import ArityError
from .utils import MethodDict
from .types import Recur, Closure

_log = logging.getLogger(__name__)


def special(fun):
    setattr(fun, '_special', True)
    return fun


class Evaluator(object):

    _log = logging.getLogger('Evaluator')
    lookup = MethodDict()

    def __init__(self, env=None):
        self._envs = [env or Environment({
            '+': lambda *args: sum(args),
            '-': lambda left, *right: reduce(lambda l, r: l - r, right, left),
            '*': lambda *args: reduce(operator.mul, args),
            '%': operator.mod,
            '=': operator.eq,
            '!=': operator.ne,
            '<': operator.lt,
            '>': operator.gt,
            '<=': operator.le,
            '>=': operator.ge,
            'eq?': operator.is_,
            'set!': self.setbang,
            'if': self.if_,
            'define': self.define,
            'eval': self.eval,
            'quote': self.quote,
            'lambda': self.lambda_,
            'list': self.list,
            'car': self.car,
            'cdr': self.cdr,
            'recur': self.recur,
            'let': self.let,
            'cons': self.cons,
            'nil': None,
        }, parent=PythonBuiltins())]

    def eval(self, obj, *, env=None):
        self._log.debug('eval: %s', obj)
        evaluator = self.lookup.get(type(obj))

        if evaluator:
            return evaluator(self, obj, env or self._envs[-1])

        return obj

    @lookup.annotate(types.Package)
    def package(self, pkg, env):
        value = None

        for expr in pkg:
            value = self.eval(expr)

        return value

    @lookup.annotate(types.Cons)
    def sexpr(self, cons, env):
        values = (c.car for c in cons)
        fun = self.eval(next(values))

        if getattr(fun, '_special', False):
            return fun(*tuple(values))

        return fun(*tuple(map(self.eval, values)))

    @lookup.annotate(types.Symbol)
    def symbol(self, symbol, env):
        return env[symbol.name]

    @special
    def setbang(self, symbol, value):
        if not isinstance(symbol, types.Symbol):
            raise TypeError("'{}' is not a symbol".format(symbol))

        for env in reversed(self._envs):
            if symbol.name in env:
                env[symbol.name] = self.eval(value)
                break

        else:
            raise NameError("'{}' not defined".format(symbol.name))

    @special
    def if_(self, pred, then, else_=types.Nil):
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
            value.name = symbol.name

        elif not isinstance(symbol, types.Symbol):
            raise TypeError("{!r} is not a symbol".format(symbol))

        elif len(value) > 1:
            raise ArityError('expected 1 argument, got {}'.format(
                len(value)))

        else:
            value = self.eval(value[0])

        self._envs[-1][symbol.name] = value

        if isinstance(value, Closure):
            self._optimize_tail_calls(value)

    @special
    def quote(self, value):
        return value

    @special
    def lambda_(self, args, *body):
        if args is types.Nil:
            args = ()

        else:
            args = tuple(map(lambda cons: cons.car.name, args))

        return Closure(
            args=args, body=types.Package(body), evaluator=self,
            env=self._envs[-1]
        )

    @special
    def recur(self, *args):
        return Recur(tuple(map(self.eval, args)))

    def list(self, *args):
        cons = head = types.Cons(args[0])

        for arg in args[1:]:
            cons.cdr = types.Cons(arg)
            cons = cons.cdr

        return head

    def car(self, cons):
        return cons.car

    def cdr(self, cons):
        return cons.cdr

    @special
    def let(self, vars, *body):
        env = Environment(parent=self._envs[-1])
        with self.over(env):
            cons = vars
            while cons is not types.Nil:
                name = cons.car.name
                value = self.eval(cons.cdr.car)
                env[name] = value

                if isinstance(value, Closure):
                    self._optimize_tail_calls(value)

                cons = cons.cdr.cdr

            return self.eval(types.Package(body))

    def cons(self, car, cdr):
        return types.Cons(car, cdr)

    @contextmanager
    def over(self, env):
        self._envs.append(env)
        yield
        self._envs.pop()

    def _optimize_tail_calls(self, closure):
        if isinstance(closure.body, types.Package):
            cons = closure.body[-1]

        elif isinstance(closure.body, types.Cons):
            cons = closure.body

        else:
            return

        pos = 0
        calls = 0
        head = cons
        prev = []
        specials = {
            self.if_: {2, 3},
            self.let: {2},
        }

        while cons is not types.Nil:
            if type(cons.car) is types.Symbol and pos == 0:
                try:
                    value = closure.env[cons.car.name]

                except NameError:
                    # Free variables, no way to know what happens with these
                    calls += 1

                else:
                    if (
                        # Obvious
                        value is closure and
                        # All previous calls, if any, have been special
                        calls == 0 and
                        (
                            # Self is body
                            not prev or
                            # Previous call was special and Self is in correct
                            # position
                            prev[-1][2] in specials[closure.env[prev[-1][0].car.name]]
                        )
                    ):
                        # Tail position!
                        cons.car = types.Symbol('recur')

                    if value in specials:
                        pass

                    else:
                        calls += 1

            elif type(cons.car) is types.Cons:
                prev.append((head, cons, pos, calls))
                head = cons = cons.car
                pos = 0
                continue

            if cons.cdr is types.Nil and prev:
                head, cons, pos, calls = prev.pop()

            pos += 1
            cons = cons.cdr

        _log.debug('tail call optimized: %s', closure.body)
