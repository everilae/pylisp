# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function


def tests():
    from .parser import Parser
    from .evaluator import Evaluator
    from .compiler import Compiler

    p = Parser("""
    (asdf    1 2 3 4 5  1e66 "asdf"     "qwer"   (asdf asdf asdf))
    """)
    p.parse()

    p = Parser("""
    "asdf \\"hehheh\\" more"
    """).parse()

    Evaluator().eval(Compiler("""(print (+ 1 2 3))""").compile())

    Evaluator().eval(Compiler("""
        (define a 1)
        (print a)
        (set! a 2)
        (print a)
    """).compile())

    try:
        Evaluator().eval(Compiler("""(set! a 1)""").compile())

    except NameError:
        pass


if __name__ == '__main__':
    tests()
