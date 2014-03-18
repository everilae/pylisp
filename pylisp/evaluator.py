# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import logging
from functools import reduce
from contextlib import contextmanager
import operator
from . import ir
from .closure import Closure, PythonBuiltins
from .utils import MethodDict
from inspect import getfullargspec, ismethod


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


# Introspection hacks for less recursion depth
no_eval = object()
re_eval = object()
do_eval = object()


class Evaluator(object):

    _log = logging.getLogger('Evaluator')
    ir_lookup = MethodDict()

    def __init__(self, closure=None):
        self._closures = [closure or Closure({
            '+': lambda *args: sum(args),
            '-': lambda left, *right: reduce(operator.sub, right, left),
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
            'nil': None,
            'car': self.car,
            'cdr': self.cdr,
        }, parent=PythonBuiltins())]

    def eval(self, code, *, closure=None):
        self._log.debug('eval: %s', code)
        return self._eval(code, closure=closure)

    def _eval(self, node, *, closure=None):
        get = self.ir_lookup.get
        closure = closure or self._closures[-1]
        done = False

        while isinstance(node, ir.Node) and not done:
            node_type = type(node)
            evaluator_method = get(node_type)
            argspec = getfullargspec(evaluator_method)

            node = evaluator_method(self, node, closure)
            done = argspec.annotations.get('return') is not re_eval

        return node

    @ir_lookup.annotate(ir.Package)
    def module(self, node, closure):
        value = None

        for expr in node.body:
            value = self._eval(expr)

        return value

    @ir_lookup.annotate(ir.List)
    def list(self, node, closure):
        fun = node.body[0]

        if isinstance(fun, ir.Node):
            fun = self._eval(fun)

        # FIXME: make function evaluation sensible
        try:
            argspec = getfullargspec(fun)
            annotations = argspec.annotations

        except TypeError:
            annotations = None

        # Edge case, speeds up most calls
        if not annotations:
            return fun(*map(self._eval, node.body[1:]))

        def eval_arg(name_arg):
            name, arg = name_arg

            if annotations.get(name) is no_eval:
                return arg

            return self._eval(arg)

        args = argspec.args

        if ismethod(fun):
            # Strip 'self', 'cls' and such
            args = args[1:]

        value = fun(*map(eval_arg, zip(iter(args), node.body[1:])))

        if annotations.get('return') is re_eval:
            value = self._eval(value)

        return value

    @ir_lookup.annotate(ir.Cons)
    def cons(self, node, closure) -> re_eval:
        return node.car

    @ir_lookup.annotate(ir.Str)
    def str(self, node, closure):
        return node.value

    @ir_lookup.annotate(ir.Symbol)
    def symbol(self, node, closure):
        return closure[node.name]

    @ir_lookup.annotate(ir.Number)
    def number(self, node, closure):
        return node.value

    def setbang(self, cons: no_eval, value):
        if not isinstance(cons.car, ir.Symbol):
            raise TypeError("'{}' is not a symbol".format(cons.car))

        symbol = cons.car

        if symbol.name in self._closures[-1]:
            self._closures[-1][symbol.name] = value

        else:
            raise NameError("'{}' not defined".format(symbol.name))

    def if_(self, pred, then: no_eval, else_: no_eval =ir.Nil) -> re_eval:
        if pred:
            return then

        else:
            return else_

    def define(self, cons: no_eval, value):
        if not isinstance(cons.car, ir.Symbol):
            raise TypeError("'{}' is not a symbol".format(cons.car))

        symbol = cons.car
        self._closures[-1][symbol.name] = value

    def quote(self, value: no_eval):
        if isinstance(value, ir.Cons):
            return value.car

        return value

    def lambda_(self, args: no_eval, body: no_eval):
        return FunctionDef(
            args=list(map(lambda cons: cons.car.name, args.car)),
            body=body, evaluator=self,
            closure=self._closures[-1]
        )

    @contextmanager
    def over(self, closure):
        self._closures.append(closure)
        yield
        self._closures.pop()

    def list(self, *args):
        list_ = ir.List()

        for arg in args:
            list_.append(arg)

        return list_

    def car(self, list_):
        return list_[0].car

    def cdr(self, list_):
        # FIXME: This should be as simple as returning the cdr
        new_list_ = ir.List()

        for cons in list_[0].cdr:
            new_list_.append(cons)

        return new_list_
