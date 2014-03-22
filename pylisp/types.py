from .env import Environment
from .exceptions import ArityError


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

    def __call__(self, *args):
        if len(self.args) != len(args):
            raise ArityError('expected {} arguments, got {}'.format(
                len(self.args), len(args)))

        env = Environment(dict(zip(self.args, args)), parent=self.env)

        with self.evaluator.over(env):
            value = self.evaluator.eval(self.body)

            while type(value) is Recur:
                env.update(zip(self.args, value.args))
                value = self.evaluator.eval(self.body)

            return value
