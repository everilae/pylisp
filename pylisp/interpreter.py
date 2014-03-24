# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
import copy

import logging
from functools import reduce, partial
from contextlib import contextmanager
import operator
from . import types 
from .env import Environment, PythonBuiltins
from .utils import MethodDict
from .types import Recur, Procedure, Continuation

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
        self._envs = [
            env or Environment(
                {
                    types.getsymbol('nil'): None,
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
                    types.getsymbol('let'): self.let,
                    types.getsymbol('cons'): self.cons,
                    types.getsymbol('begin'): self.begin,
                    types.getsymbol('call/cc'): self.call_cc,
                },
                env=PythonBuiltins()
            )
        ]

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

            env = env.env

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
            args = tuple(c.car for c in args)

        return Procedure(None, args, body, self._envs[-1])

    @special
    def call_cc(self, fun):
        self.expr(types.Cons(fun, types.Cons(self._currcontinuation)))

    @special
    def recur(self, proc, *args):
        # Build a new calling environment
        env = Environment(dict(zip(proc.args, map(self.eval, args))),
                          env=proc.env)
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

    def cdr(self, cons):
        return cons.cdr

    @special
    def let(self, defs, *body):
        env = Environment(env=self._envs[-1])

        with self.over(env):
            for d in defs:
                symbol = d.car.car
                value = d.car.cdr.car
                env[symbol] = self.eval(value)

                if isinstance(value, Procedure):
                    self._optimize_tail_calls(value)

            return self._run_continuation(Continuation(env, body))

    def cons(self, car, cdr):
        return types.Cons(car, cdr)

    @contextmanager
    def over(self, env):
        self._envs.append(env)

        try:
            yield

        finally:
            self._envs.pop()

    def _call_procedure(self, proc, *args):
        if len(proc.args) != len(args):
            raise TypeError('expected {} arguments, got {}'.format(
                len(proc.args), len(args)))

        env = Environment(dict(zip(proc.args, args)), env=proc.env)
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
                        # Tail position! Do some rewriting
                        cons.car = self.recur
                        # Insert a reference to procedure as 1. arg
                        cons.cdr = types.Cons(proc, cons.cdr)

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
