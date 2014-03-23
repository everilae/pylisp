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
from .types import Recur, Procedure

_log = logging.getLogger(__name__)


def special(fun):
    setattr(fun, '_special', True)
    return fun


class Evaluator(object):

    _log = _log.getChild('Evaluator')
    lookup = MethodDict()

    def __init__(self, env=None):
        self._envs = [env or Environment({
            types.getsymbol('+'): lambda *args: sum(args),
            types.getsymbol('-'): lambda left, *right: reduce(lambda l, r: l - r, right, left),
            types.getsymbol('*'): lambda *args: reduce(operator.mul, args),
            types.getsymbol('%'): operator.mod,
            types.getsymbol('='): operator.eq,
            types.getsymbol('!='): operator.ne,
            types.getsymbol('<'): operator.lt,
            types.getsymbol('>'): operator.gt,
            types.getsymbol('<='): operator.le,
            types.getsymbol('>='): operator.ge,
            types.getsymbol('eq?'): operator.is_,
            types.getsymbol('set!'): self.setbang,
            types.getsymbol('if'): self.if_,
            types.getsymbol('define'): self.define,
            types.getsymbol('eval'): self.eval,
            types.getsymbol('quote'): self.quote,
            types.getsymbol('lambda'): self.lambda_,
            types.getsymbol('list'): self.list,
            types.getsymbol('car'): self.car,
            types.getsymbol('cdr'): self.cdr,
            types.getsymbol('recur'): self.recur,
            types.getsymbol('let'): self.let,
            types.getsymbol('cons'): self.cons,
            types.getsymbol('begin'): self.begin,
            types.getsymbol('nil'): None,
        }, parent=PythonBuiltins())]

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

        if getattr(fun, '_special', False):
            return fun(*values)

        return fun(*map(self.eval, values))

    @lookup.annotate(types.Symbol)
    def symbol(self, symbol):
        return self._envs[-1][symbol]

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

        env = self._envs[-1]
        while env:
            if symbol in env:
                env[symbol] = self.eval(value)
                return

            env = env.parent

        raise NameError("'{}' not defined".format(symbol))

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
            value.name = symbol

        else:
            value = self.eval(value[0])

        self._envs[-1][symbol] = value
        self._log.debug('define: %s', self._envs[-1])

        if isinstance(value, Procedure):
            self._optimize_tail_calls(value)

    @special
    def quote(self, value):
        return value

    @special
    def lambda_(self, args, *body):
        if args is types.Nil:
            args = ()

        else:
            args = tuple(map(lambda cons: cons.car, args))

        return Procedure(
            None, args, body,
            evaluator=self, env=self._envs[-1]
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
                value = self.eval(cons.cdr.car)
                env[cons.car] = value

                if isinstance(value, Procedure):
                    self._optimize_tail_calls(value)

                cons = cons.cdr.cdr

            return self.eval(types.Package(body))

    def cons(self, car, cdr):
        return types.Cons(car, cdr)

    @contextmanager
    def over(self, env):
        self._envs.append(env)

        try:
            yield

        finally:
            self._envs.pop()

    def _optimize_tail_calls(self, proc):
        if not isinstance(proc.body[-1], types.Cons):
            return

        pos = 0
        calls = 0
        cons = proc.body[-1]
        head = cons
        prev = []
        specials = {
            self.if_: {2, 3},
            self.let: {-1},
            self.lambda_: {-1},
        }

        while cons is not types.Nil:
            if type(cons.car) is types.Symbol and pos == 0:
                try:
                    value = proc.env[cons.car]

                except NameError:
                    # Free variables, no way to know what happens with these
                    calls += 1

                else:
                    if (
                        # Obvious
                        value is proc and
                        # All previous calls, if any, have been special
                        calls == 0 and
                        (
                            # Self is body
                            not prev or
                            # Previous call was special and Self is in correct
                            # position
                            prev[-1][2] in specials[proc.env[prev[-1][0].car]]
                        )
                    ):
                        # Tail position!
                        cons.car = types.getsymbol('recur')

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

        _log.debug('tail call optimized: %s', proc.body)
