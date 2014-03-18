# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

from io import StringIO
import string
import logging
from functools import reduce
from contextlib import contextmanager
import builtins
import operator
from threading import Lock


class PythonBuiltins(object):

    def __getitem__(self, name):
        attr = None
        if '.' in name:
            name, attr = name.split('.', 1)

        if hasattr(builtins, name):
            value = getattr(builtins, name)

            if attr:
                value = getattr(value, attr)

        else:
            raise NameError(name)

        return value

    def __contains__(self, name):
        return hasattr(builtins, name)

    def __repr__(self):
        return repr(builtins)


class Closure(object):

    def __init__(self, initial=None, parent=None):
        self.values = initial or {}
        self.parent = parent

    def __getitem__(self, name):
        if name in self.values:
            return self.values[name]

        elif self.parent:
            return self.parent[name]

        raise NameError(name)

    def __setitem__(self, name, value):
        self.values[name] = value

    def __contains__(self, name):
        return name in self.values or self.parent and name in self.parent

    def __repr__(self):
        return '<Closure {!r} at 0x{:x}, parent: {!r}>'.format(
            self.values, id(self), self.parent)


class ir(object):


    class Node(object):
        def __init__(self, lineno=None, col_offset=None):
            self.lineno = lineno
            self.col_offset = col_offset


    class NodeCollection(Node):
        def __init__(self, body=None, lineno=None, col_offset=None):
            self.body = body or []
            super().__init__(lineno=lineno, col_offset=col_offset)

        def __repr__(self):
            return ' '.join(map(repr, self.body))

        def append(self, node):
            self.body.append(node)

        def __iter__(self):
            yield from self.body


    class Package(NodeCollection):
        pass


    class List(NodeCollection):
        def __repr__(self):
            return '({})'.format(super().__repr__())

        def append(self, node):
            cons = ir.Cons(node,
                           lineno=getattr(node, 'lineno', None),
                           col_offset=getattr(node, 'col_offset', None))

            if self.body:
                self.body[-1].cdr = cons

            super().append(cons)


    Nil = Node()


    class Cons(Node):
        def __init__(self, car, cdr=None, lineno=None, col_offset=None):
            self.car = car
            self.cdr = cdr or ir.Nil
            super().__init__(lineno=lineno, col_offset=col_offset)

        def __repr__(self):
            return self.car.__repr__()

        def __str__(self):
            return self.car.__str__()


    class Str(Node):
        def __init__(self, value, lineno=None, col_offset=None):
            self.value = value
            super().__init__(lineno=lineno, col_offset=col_offset)

        def __repr__(self):
            return '"{}"'.format(self.value)


    class Symbol(Node):
        def __init__(self, name, lineno=None, col_offset=None):
            self.name = name
            super().__init__(lineno=lineno, col_offset=col_offset)

        def __repr__(self):
            return self.name

        def __eq__(self, other):
            return isinstance(other, ir.Symbol) and self.name == other.name


    class Number(Node):
        def __init__(self, value, lineno=None, col_offset=None):
            self.value = value
            super().__init__(lineno=lineno, col_offset=col_offset)

        def __repr__(self):
            return '{}'.format(self.value)


class MethodDict(dict):

    def annotate(self, identifier):
        def decorator(fun):
            self[identifier] = fun
            return fun

        return decorator


class Parser(object):

    _log = logging.getLogger('Parser')

    parsers = MethodDict()

    def __init__(self, source):
        self.source = source
        self.ir = [ir.Package()]

        self._line = None
        self._lineno = None
        self._linepos = None

        if isinstance(self.source, str):
            self.source = StringIO(self.source)

    def parse(self):
        self._log.debug('parsing %r', self.source)

        for lineno, line in enumerate(self.source, 1):
            self._line = line
            self._lineno = lineno
            self._linepos = 0
            self._linelen = len(line)
            # Start parsing for this line
            while self._linepos < self._linelen:
                self._parse()

        if not isinstance(self.ir[-1], ir.Package):
            raise self._syntax_error("unexpected EOF")

        return self.ir[-1]

    def _parse(self):
        chr_ = self._line[self._linepos]

        while chr_ in string.whitespace:
            self._linepos += 1
            chr_ = self._line[self._linepos]
            continue

        self.parsers.get(chr_, Parser.create_symbol)(self)

    def _syntax_error(self, msg):
        return SyntaxError('{}, line {} col {}'.format(
            msg, self._lineno, self._linepos))

    def _pop_quote(self):
        if getattr(self.ir[-1], 'is_quote', False):
            self.ir.pop()

    @parsers.annotate(';')
    def comment(self):
        self._linepos = self._linelen

    @parsers.annotate("'")
    def quote(self):
        quote = ir.Symbol('quote', lineno=self._lineno,
                          col_offset=self._linepos)
        self.begin_list(quote=True)
        self.ir[-1].append(quote)

    @parsers.annotate('(')
    def begin_list(self, quote=False):
        list_ = ir.List(lineno=self._lineno, col_offset=self._linepos)
        setattr(list_, 'is_quote', quote)
        self.ir[-1].append(list_)
        self.ir.append(list_)
        self._linepos += 1

    @parsers.annotate(')')
    def end_list(self):
        if not isinstance(self.ir[-1], ir.List):
            raise self._syntax_error('unexpected end of list')

        self.ir.pop()
        self._pop_quote()
        self._linepos += 1

    @parsers.annotate('"')
    def create_str(self):
        done = False
        start = self._linepos + 1
        end = self._line.find('"', start)

        while not done and end < self._linelen:
            if end == -1:
                raise self._syntax_error('unterminated string')

            if self._line[end - 1] != '\\':
                done = True

            else:
                end = self._line.find('"', end + 1)

        s = ir.Str(self._line[start:end], lineno=self._lineno,
                   col_offset=self._linepos)
        self.ir[-1].append(s)
        self._pop_quote()
        self._linepos = end + 1

    def create_symbol(self):
        start = self._linepos
        end = start
        non_symbol_chrs = frozenset(string.whitespace + ')')

        while end < self._linelen and self._line[end] not in non_symbol_chrs:
            end += 1

        value = self._line[start:end]

        try:
            try:
                value = int(value)

            except ValueError:
                value = float(value)

            symbol = ir.Number

        except ValueError:
            symbol = ir.Symbol

        self.ir[-1].append(symbol(value, lineno=self._lineno,
                                  col_offset=self._linepos))
        self._pop_quote()
        self._linepos = end


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

        fun = node.body[0]
        if isinstance(fun, ir.Node):
            fun = self._eval(fun)

        self._log.debug('fun: %s', fun)

        if getattr(fun, '_no_eval', False):
            return fun(*node.body[1:])

        return fun(*map(self._eval, node.body[1:]))

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


def tests():
    p = Parser("""
    (asdf    1 2 3 4 5  1e66 "asdf"     "qwer"   (asdf asdf asdf))
    """)
    print(p.parse())

    p = Parser("""
    "asdf \\"hehheh\\" more"
    """)
    print(p.parse())

    Evaluator().eval(Parser("""(print (+ 1 2 3))""").parse())

    Evaluator().eval(Parser("""
        (define a 1)
        (print a)
        (set! a 2)
        (print a)""").parse())

    Evaluator().eval(Parser("""(set! a 1)""").parse())


if __name__ == '__main__':
    #logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger(__name__)

    import os

    if False:
        from argparse import ArgumentParser, FileType

        argparser = ArgumentParser()
        argparser.add_argument('file', type=FileType('r'))
        args = argparser.parse_args()

    try:
        import readline
        histfile = os.path.join(os.path.expanduser("~"), ".splhist")
        try:
            readline.read_history_file(histfile)

        except IOError:
            pass

        import atexit
        atexit.register(readline.write_history_file, histfile)
        del histfile

    except ImportError:
        log.info('readline not available')

    e = Evaluator()

    if False and args.file:
        import sys
        sys.exit(e.eval(Parser(args.file).parse()))

    print('Silly Python Lisp 0 on {[0]}'.format(os.uname()))
    while True:
        try:
            source = input('>>> ')

        except EOFError:
            print('quit')
            break

        if not source:
            continue

        try:
            code = Parser(source).parse()

        except Exception:
            log.exception('Parser error')
            continue

        try:
            print(e.eval(code))

        except Exception:
            log.exception('Evaluation error')
            continue
