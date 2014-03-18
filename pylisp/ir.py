# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function


class Node(object):
    def __init__(self, lineno=None, col_offset=None):
        self.lineno = lineno
        self.col_offset = col_offset


class NodeCollection(Node):
    def __init__(self, body=None, lineno=None, col_offset=None):
        self.body = body or []
        super().__init__(lineno=lineno, col_offset=col_offset)

    def __repr__(self):
        return ' '.join(map(repr, self))

    def append(self, node):
        self.body.append(node)

    def __iter__(self):
        yield from self.body

    def __getitem__(self, index):
        return self.body[index]


class Package(NodeCollection):
    pass


class SExpr(Node):
    """
    SExpr is a compile time helper type that makes handling conses easier.
    It keeps track of current expressions head and tail in order to allow for
    easy appending.
    """

    def __init__(self, cons=None, lineno=None, col_offset=None):
        self.head = cons
        self.tail = cons
        super().__init__(lineno=lineno, col_offset=col_offset)

    def __repr__(self):
        if self.head:
            return repr(self.head)

        return '()'

    def append(self, node):
        lineno = getattr(node, 'lineno', None)
        col_offset = getattr(node, 'col_offset', None)

        if isinstance(node, SExpr):
            node = node.head

        node = Cons(node, lineno=lineno, col_offset=lineno)

        if not self.head:
            self.head = node
            self.tail = node

        else:
            self.tail.cdr = node
            self.tail = node


class Cons(Node):
    def __init__(self, car, cdr=None, lineno=None, col_offset=None):
        self.car = car
        self.cdr = cdr or Nil
        super().__init__(lineno=lineno, col_offset=col_offset)

    def __repr__(self):
        return '({})'.format(
            ' '.join(map(lambda cons: repr(cons.car), iter(self))))

    def __iter__(self):
        cons = self

        while cons is not Nil:
            yield cons
            cons = cons.cdr


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
        return isinstance(other, Symbol) and self.name == other.name


class Number(Node):
    def __init__(self, value, lineno=None, col_offset=None):
        self.value = value
        super().__init__(lineno=lineno, col_offset=col_offset)

    def __repr__(self):
        return '{}'.format(self.value)


Nil = Symbol('nil')
