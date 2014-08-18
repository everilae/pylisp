from threading import Lock


class Recur(object):
    def __init__(self, args):
        self.args = args


class Procedure(object):

    __slots__ = ('name', 'args', 'body', 'env')

    def __init__(self, name, args, body, env):
        if not body:
            raise ValueError('procedure without a body')

        self.name = name
        self.args = args
        self.body = body
        self.env = env


class Continuation(object):

    __slots__ = ('env', 'exprs', 'next')

    def __init__(self, env, exprs, next=0):
        self.env = env
        self.exprs = exprs
        self.next = next


class Symbol(object):

    __slots__ = ('name',)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


class Cons(object):

    __slots__ = ('car', 'cdr')

    def __init__(self, car, cdr=None):
        self.car = car
        self.cdr = cdr

    def __repr__(self):
        return '({})'.format(' '.join(self))

    def __iter__(self):
        value = self

        while isinstance(value, Cons):
            yield value
            value = value.cdr
