from .parser import Parser
from . import ir
from . import types
from .utils import MethodDict


class Compiler(object):

    compilers = MethodDict()

    def __init__(self, source):
        self.parser = Parser(source)

    def compile(self):
        root = self.parser.parse()
        return self._compile(root)

    def _compile(self, node):
        return self.compilers.get(type(node), lambda v: v)(self, node)
    
    @compilers.annotate(ir.Package)
    def package(self, node):
        return types.Package(self._compile(n) for n in node)

    @compilers.annotate(ir.Cons)
    def cons(self, node):
        return types.Cons(
            self._compile(node.car),
            self._compile(node.cdr)
        )

    @compilers.annotate(ir.Symbol)
    def symbol(self, node):
        return types.getsymbol(node.name)

    @compilers.annotate(ir.Number)
    def number(self, node):
        return node.value

    @compilers.annotate(ir.Str)
    def str(self, node):
        return node.value
