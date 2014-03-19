# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import logging
from functools import reduce
from contextlib import contextmanager
import operator
from . import ir
from .closure import Closure, PythonBuiltins
from .utils import MethodDict

_log = logging.getLogger(__name__)


class ArityError(Exception):
    pass


class Recur(object):
    def __init__(self, args):
        self.args = args


class FunctionDef(object):

    def __init__(self, name=None, args=None, body=None,
                 evaluator=None, closure=None):
        self.name = name
        self.args = args
        self.body = body
        self.evaluator = evaluator
        self.closure = closure

        self._tco = False

    def __call__(self, *args):
        if len(self.args) != len(args):
            raise ArityError('expected {} arguments, got {}'.format(
                len(self.args), len(args)))

        if not self._tco:
            self.optimize_tail_calls()

        closure = Closure(dict(zip(self.args, args)), parent=self.closure)

        with self.evaluator.over(closure):
            value = self.evaluator.eval(self.body)

            while type(value) is Recur:
                closure.update(zip(self.args, value.args))
                value = self.evaluator.eval(self.body)

            return value

    def optimize_tail_calls(self):
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
                    value = self.closure[cons.car.name]

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
                            prev[-1][2] in specials[self.closure[prev[-1][0].car.name]]
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

    def __init__(self, closure=None):
        self._closures = [closure or Closure({
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
        }, parent=PythonBuiltins())]

    def eval(self, code, *, closure=None):
        self._log.debug('eval: %s', code)
        return self._eval(code, closure=closure)

    def _eval(self, node, *, closure=None):
        if isinstance(node, ir.Node):
            return self.ir_lookup.get(type(node))(
                self, node, closure or self._closures[-1])

        return node

    @ir_lookup.annotate(ir.Package)
    def module(self, node, closure):
        value = None

        for expr in node.body:
            value = self._eval(expr)

        return value

    @ir_lookup.annotate(ir.Cons)
    def sexpr(self, cons, closure):
        self._log.debug('list: %s', cons)

        values = (c.car for c in cons)
        fun = next(values)
        if isinstance(fun, ir.Node):
            fun = self._eval(fun)

        self._log.debug('fun: %s', fun)

        if getattr(fun, '_special', False):
            return fun(*tuple(values))

        return fun(*tuple(map(self._eval, values)))

    @ir_lookup.annotate(ir.Str)
    def str(self, node, closure):
        return node.value

    @ir_lookup.annotate(ir.Symbol)
    def symbol(self, node, closure):
        return closure[node.name]

    @ir_lookup.annotate(ir.Number)
    def number(self, node, closure):
        return node.value

    @special
    def setbang(self, symbol, value):
        if not isinstance(symbol, ir.Symbol):
            raise TypeError("'{}' is not a symbol".format(symbol))

        if symbol.name in self._closures[-1]:
            self._closures[-1][symbol.name] = self._eval(value)

        else:
            raise NameError("'{}' not defined".format(symbol.name))

    @special
    def if_(self, pred, then, else_=ir.Nil):
        if self._eval(pred):
            return self._eval(then)

        else:
            return self._eval(else_)

    @special
    def define(self, symbol, value):
        if not isinstance(symbol, ir.Symbol):
            raise TypeError("'{}' is not a symbol".format(symbol))

        value = self._eval(value)
        self._closures[-1][symbol.name] = value

    @special
    def quote(self, value):
        return value

    @special
    def lambda_(self, args, body):
        return FunctionDef(
            args=list(map(lambda cons: cons.car.name, args)),
            body=body, evaluator=self,
            closure=self._closures[-1]
        )

    @special
    def recur(self, *args):
        return Recur(tuple(map(self._eval, args)))

    @contextmanager
    def over(self, closure):
        self._closures.append(closure)
        yield
        self._closures.pop()

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
                value = self._eval(cons.cdr.car)
                yield (name, value)
                cons = cons.cdr.cdr

        closure = Closure(parent=self._closures[-1])
        with self.over(closure):
            closure.update(dict((k, v) for k, v in ivar(vars)))
            return self._eval(body)
