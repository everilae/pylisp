from threading import Lock


class Recur(object):
    def __init__(self, args):
        self.args = args


class Procedure(object):

    def __init__(self, name, args, body, *,
                 env=None):
        if not body:
            raise ValueError('procedure without a body')

        self.name = name
        self.args = args
        self.body = body
        self.env = env


class Symbol(object):

    _lock = Lock()
    _table = {}

    @classmethod
    def get(cls, name):
        with cls._lock:
            try:
                return cls._table[name]

            except KeyError:
                symbol = cls(name)
                cls._table[name] = symbol
                return symbol

    __slots__ = ['name']

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


def getsymbol(name):
    return Symbol.get(name)


Nil = Symbol.get('nil')


class Cons(object):

    __slots__ = ['car', 'cdr']

    def __init__(self, car, cdr=Nil):
        self.car = car
        self.cdr = cdr

    def __repr__(self):
        values = []

        for value in self:
            values.append(repr(value.car))

        if value.cdr is not Nil:
            values.extend(['.', repr(value.cdr)])

        return '({})'.format(' '.join(values))

    def __iter__(self):
        value = self

        while isinstance(value, Cons):
            yield value
            value = value.cdr
