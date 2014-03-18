# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function


def tests():
    from .parser import Parser
    from .evaluator import Evaluator

    p = Parser("""
    (asdf    1 2 3 4 5  1e66 "asdf"     "qwer"   (asdf asdf asdf))
    """)
    p.parse()

    p = Parser("""
    "asdf \\"hehheh\\" more"
    """).parse()

    Evaluator().eval(Parser("""(print (+ 1 2 3))""").parse())

    Evaluator().eval(Parser("""
        (define a 1)
        (print a)
        (set! a 2)
        (print a)
    """).parse())

    try:
        Evaluator().eval(Parser("""(set! a 1)""").parse())

    except NameError:
        pass


if __name__ == '__main__':
    tests()
