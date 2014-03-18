# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import logging
from .evaluator import Evaluator
from .parser import Parser


def repl():
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

if __name__ == '__main__':
    repl()
