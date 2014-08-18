import ast
from .parser import Parser
from . import ir
from . import types
from .utils import MethodDict


class _Compiler(object):

    compilers = {}

    def __init__(self, source):
        self.parser = Parser(source)

    def compile(self):
        root = self.parser.parse()
        return self._compile(root)

    def _compile(self, node):
        return self.compilers.get(type(node), self.__class__._notimplemented)(self, node)

    def _notimplemented(self, node):
        raise NotImplementedError(node)


class Compiler(_Compiler):

    compilers = MethodDict()

    @compilers.annotate(ir.Package)
    def package(self, node):
        begin = types.Cons(types.Symbol('begin'))
        tail = begin

        for expr in node:
            tail.cdr = types.Cons(self._compile(expr))
            tail = tail.cdr

        return begin

    @compilers.annotate(ir.Cons)
    def cons(self, node):
        return types.Cons(
            self._compile(node.car),
            self._compile(node.cdr)
        )

    @compilers.annotate(ir.Symbol)
    def symbol(self, node):
        return types.Symbol(node.name)

    @compilers.annotate(ir.Number)
    def number(self, node):
        return node.value

    @compilers.annotate(ir.Str)
    def str(self, node):
        return node.value


class PyCompiler(_Compiler):

    compilers = MethodDict()
    specials = MethodDict()

    def _body(self, node):
        body = []
        for expr in node:
            compiled = self._compile(expr)
            if not isinstance(compiled,
                              (ast.Assign, ast.Return, ast.FunctionDef)):
                compiled = ast.Expr(
                    value=compiled,
                    lineno=expr.lineno,
                    col_offset=expr.col_offset
                )

            body.append(compiled)

        return body

    @compilers.annotate(ir.Package)
    def package(self, node):
        return compile(ast.Module(
            body=self._body(node),
            lineno=node.lineno,
            col_offset=node.col_offset
        ), '<input>', 'exec')

    @compilers.annotate(ir.Symbol)
    def symbol(self, symbol, ctx=ast.Load):
        return ast.Name(id=symbol.name, ctx=ctx(),
                        lineno=symbol.lineno,
                        col_offset=symbol.col_offset)

    @compilers.annotate(ir.Cons)
    def cons(self, cons):
        E = (c for c in cons)
        L = next(E).car

        if isinstance(L, ir.Symbol) and L.name in self.specials:
            return self.specials[L.name](self, E, cons.lineno, cons.col_offset)

        L = self._compile(L)
        A = list(self._compile(e.car) for e in E)

        return ast.Call(
            func=L, args=A,
            lineno=cons.lineno,
            col_offset=cons.col_offset,
            keywords=[],
            kwargs=None,
            starargs=None
        )

    @compilers.annotate(ir.Number)
    def number(self, node):
        return ast.Num(n=node.value,
                       lineno=node.lineno,
                       col_offset=node.col_offset)

    @compilers.annotate(ir.Str)
    def str(self, node):
        return ast.Str(s=node.value,
                       lineno=node.lineno,
                       col_offset=node.col_offset)

    def _functiondef(self, name, args, body, lineno, col_offset):
        args = [ast.arg(arg=c.car.name, annotation=None) for c in args]
        body = self._body(c.car for c in body)

        # Rewrite return
        body[-1] = ast.Return(
            value=body[-1].value,
            lineno=body[-1].lineno,
            col_offset=body[-1].col_offset
        )

        return ast.FunctionDef(
            name=name,
            args=ast.arguments(
                args=args,
                defaults=[],
                kw_defaults=[],
                kwarg=None,
                kwargannotation=None,
                kwonlyargs=[],
                vararg=None,
                varargannotation=None
            ),
            body=body,
            returns=None,
            decorator_list=[],
            lineno=lineno,
            col_offset=col_offset
        )

    @specials.annotate('define')
    def _define(self, rest, lineno, col_offset):
        first = next(rest)

        if isinstance(first.car, ir.Symbol):
            return ast.Assign(
                targets=[self.symbol(first.car, ctx=ast.Store)],
                value=self._compile(next(rest).car),
                lineno=lineno,
                col_offset=col_offset
            )

        elif isinstance(first.car, ir.Cons):
            itr = iter(first.car)
            name = next(itr).car.name
            args = next(itr)
            body = rest
            return self._functiondef(name, args, body, lineno, col_offset)

        else:
            raise ValueError(first.car)

    @specials.annotate('lambda')
    def lambda_(self, rest, lineno, col_offset):
        args = next(rest)
        body = rest
        return self._functiondef('#<Closure>', args, body, lineno, col_offset)
