# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import logging
from functools import reduce
from contextlib import contextmanager
import operator
from . import ir
from .closure import Closure, PythonBuiltins
from .utils import MethodDict


class ArityError(Exception):
    pass


class FunctionDef(object):

    def __init__(self, name=None, args=None, body=None,
                 evaluator=None, closure=None):
        self.name = name
        self.args = args
        self.body = body
        self.evaluator = evaluator
        self.closure = closure

    def __call__(self, *args):
        if len(self.args) != len(args):
            raise ArityError('expected {} arguments, got {}'.format(
                len(self.args), len(args)))

        closure = Closure(dict(zip(self.args, args)), parent=self.closure)

        with self.evaluator.over(closure):
            return self.evaluator.eval(self.body)


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

        self._closures[-1][symbol.name] = self._eval(value)

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
