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
        cons = Cons(node,
                    lineno=getattr(node, 'lineno', None),
                    col_offset=getattr(node, 'col_offset', None))

        if self.body:
            self.body[-1].cdr = cons

        super().append(cons)


Nil = Node()


class Cons(Node):
    def __init__(self, car, cdr=None, lineno=None, col_offset=None):
        self.car = car
        self.cdr = cdr or Nil
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
        return isinstance(other, Symbol) and self.name == other.name


class Number(Node):
    def __init__(self, value, lineno=None, col_offset=None):
        self.value = value
        super().__init__(lineno=lineno, col_offset=col_offset)

    def __repr__(self):
        return '{}'.format(self.value)
