# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import logging
from functools import reduce
from contextlib import contextmanager
import operator
from . import ir
from .env import Environment, PythonBuiltins
from .utils import MethodDict

_log = logging.getLogger(__name__)


class ArityError(Exception):
    pass


class Recur(object):
    def __init__(self, args):
        self.args = args


class Closure(object):

    def __init__(self, name=None, args=None, body=None,
                 evaluator=None, env=None):
        self.name = name
        self.args = args
        self.body = body
        self.evaluator = evaluator
        self.env = env

        self._tco = False

    def __call__(self, *args):
        if len(self.args) != len(args):
            raise ArityError('expected {} arguments, got {}'.format(
                len(self.args), len(args)))

        if not self._tco:
            self.optimize_tail_calls()

        env = Environment(dict(zip(self.args, args)), parent=self.env)

        with self.evaluator.over(env):
            value = self.evaluator.eval(self.body)

            while type(value) is Recur:
                env.update(zip(self.args, value.args))
                value = self.evaluator.eval(self.body)

            return value

    def optimize_tail_calls(self):
        if type(self.body) is not ir.Cons:
            return

        pos = 0
        calls = 0
        cons = self.body
        head = cons
        prev = []
        specials = {
            self.evaluator.if_: {2, 3},
            self.evaluator.let: {2},
        }

        while cons is not ir.Nil:
            if type(cons.car) is ir.Symbol and pos == 0:
                try:
                    value = self.env[cons.car.name]

                except NameError:
                    # Free variables, no way to know what happens with these
                    calls += 1

                else:
                    if (
                        # Obvious
                        value is self and
                        # All previous calls, if any, have been special
                        calls == 0 and
                        (
                            # Self is body
                            not prev or
                            # Previous call was special and Self is in correct
                            # position
                            prev[-1][2] in specials[self.env[prev[-1][0].car.name]]
                        )
                    ):
                        # Tail position!
                        cons.car = ir.Symbol(
                            'recur',
                            lineno=cons.car.lineno,
                            col_offset=cons.car.col_offset
                        )

                    if value in specials:
                        pass

                    else:
                        calls += 1

            elif type(cons.car) is ir.Cons:
                prev.append((head, cons, pos, calls))
                head = cons = cons.car
                pos = 0
                continue

            if cons.cdr is ir.Nil and prev:
                head, cons, pos, calls = prev.pop()

            pos += 1
            cons = cons.cdr

        self._tco = True
        _log.debug('tail call optimized: %s', self.body)


def special(fun):
    setattr(fun, '_special', True)
    return fun


class Evaluator(object):

    _log = logging.getLogger('Evaluator')
    ir_lookup = MethodDict()

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
        }, parent=PythonBuiltins())]

    def eval(self, code, *, env=None):
        self._log.debug('eval: %s', code)
        if isinstance(code, ir.Node):
            node_evaluator = self.ir_lookup.get(type(code))
            return node_evaluator(self, code, env or self._envs[-1])

        return code

    @ir_lookup.annotate(ir.Package)
    def package(self, node, env):
        value = None

        for expr in node.body:
            value = self.eval(expr)

        return value

    @ir_lookup.annotate(ir.Cons)
    def sexpr(self, cons, env):
        values = (c.car for c in cons)
        fun = next(values)
        if isinstance(fun, ir.Node):
            fun = self.eval(fun)

        if getattr(fun, '_special', False):
            return fun(*tuple(values))

        return fun(*tuple(map(self.eval, values)))

    @ir_lookup.annotate(ir.Str)
    def str(self, node, env):
        return node.value

    @ir_lookup.annotate(ir.Symbol)
    def symbol(self, node, env):
        return env[node.name]

    @ir_lookup.annotate(ir.Number)
    def number(self, node, env):
        return node.value

    @special
    def setbang(self, symbol, value):
        if not isinstance(symbol, ir.Symbol):
            raise TypeError("'{}' is not a symbol".format(symbol))

        if symbol.name in self._envs[-1]:
            self._envs[-1][symbol.name] = self.eval(value)

        else:
            raise NameError("'{}' not defined".format(symbol.name))

    @special
    def if_(self, pred, then, else_=ir.Nil):
        if self.eval(pred):
            return self.eval(then)

        else:
            return self.eval(else_)

    @special
    def define(self, symbol, value):
        if not isinstance(symbol, ir.Symbol):
            raise TypeError("'{}' is not a symbol".format(symbol))

        value = self.eval(value)
        self._envs[-1][symbol.name] = value

    @special
    def quote(self, value):
        return value

    @special
    def lambda_(self, args, body):
        return Closure(
            args=tuple(map(lambda cons: cons.car.name, args)) if args is not ir.Nil else (),
            body=body, evaluator=self,
            env=self._envs[-1]
        )

    @special
    def recur(self, *args):
        return Recur(tuple(map(self.eval, args)))

    @contextmanager
    def over(self, env):
        self._envs.append(env)
        yield
        self._envs.pop()

    def list(self, *args):
        # Using SExpr node makes constructing a list easier;
        # It handles conversions to cons etc
        list_ = ir.SExpr()

        for arg in args:
            list_.append(arg)

        return list_.head

    def car(self, cons):
        return cons.car

    def cdr(self, cons):
        return cons.cdr

    @special
    def let(self, vars, body):
        def ivar(cons):
            while cons is not ir.Nil:
                name = cons.car.name
                value = self.eval(cons.cdr.car)
                yield (name, value)
                cons = cons.cdr.cdr

        env = Environment(parent=self._envs[-1])
        with self.over(env):
            env.update(dict((k, v) for k, v in ivar(vars)))
            return self.eval(body)

    def cons(self, car, cdr):
        return ir.Cons(car, cdr)
