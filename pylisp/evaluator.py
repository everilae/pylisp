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


def no_eval(fun):
    setattr(fun, '_no_eval', True)
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

    @ir_lookup.annotate(ir.List)
    def list(self, node, closure):
        self._log.debug('list: %s', node)

        fun = node.head.car
        if isinstance(fun, ir.Node):
            fun = self._eval(fun)

        self._log.debug('fun: %s', fun)

        if getattr(fun, '_no_eval', False):
            return fun(*tuple(iter(node.head.cdr)))

        return fun(*tuple(map(self._eval, iter(node.head.cdr))))

    @ir_lookup.annotate(ir.Cons)
    def cons(self, node, closure):
        return self._eval(node.car)

    @ir_lookup.annotate(ir.Str)
    def str(self, node, closure):
        return node.value

    @ir_lookup.annotate(ir.Symbol)
    def symbol(self, node, closure):
        return closure[node.name]

    @ir_lookup.annotate(ir.Number)
    def number(self, node, closure):
        return node.value

    @no_eval
    def setbang(self, cons, value):
        if not isinstance(cons.car, ir.Symbol):
            raise TypeError("'{}' is not a symbol".format(cons.car))

        symbol = cons.car

        if symbol.name in self._closures[-1]:
            self._closures[-1][symbol.name] = self._eval(value)

        else:
            raise NameError("'{}' not defined".format(symbol.name))

    @no_eval
    def if_(self, pred, then, else_=ir.Nil):
        if self._eval(pred):
            return self._eval(then)

        else:
            return self._eval(else_)

    @no_eval
    def define(self, cons, value):
        if not isinstance(cons.car, ir.Symbol):
            raise TypeError("'{}' is not a symbol".format(cons.car))

        symbol = cons.car

        self._closures[-1][symbol.name] = self._eval(value)

    @no_eval
    def quote(self, value):
        if isinstance(value, ir.Cons):
            return value.car

        return value

    @no_eval
    def lambda_(self, args, body):
        return FunctionDef(
            args=list(map(lambda cons: cons.car.name, args.car)),
            body=body, evaluator=self,
            closure=self._closures[-1]
        )

    @contextmanager
    def over(self, closure):
        self._log.debug(closure)
        self._closures.append(closure)
        yield
        self._closures.pop()

    def list(self, *args):
        list_ = ir.List()

        for arg in args:
            list_.append(arg)

        return list_


