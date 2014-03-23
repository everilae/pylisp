# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

from argparse import ArgumentParser, FileType
import sys
import os
import logging
from .evaluator import Evaluator
from .compiler import Compiler


def repl():
    argparser = ArgumentParser("Silly Python Lisp")
    argparser.add_argument(
        '-d', '--debug', action='store_true',
        help="debug output")
    argparser.add_argument(
        'file', type=FileType('r'), nargs='?',
        help="program read from file")

    args = argparser.parse_args()
    e = Evaluator()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    log = logging.getLogger(__name__)

    if args.file:
        sys.exit(e.eval(Parser(args.file).parse()))

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
        pass

    print('Silly Python Lisp 0 on {[0]}'.format(os.uname()))

    while True:
        try:
            source = input('>>> ')

        except EOFError:
            print('quit')
            break

        except KeyboardInterrupt as ki:
            print(ki)
            continue

        if not source:
            continue

        try:
            code = Compiler(source).compile()

        except Exception:
            log.exception('Compiler error')
            continue

        except KeyboardInterrupt as ki:
            print(ki)
            continue

        try:
            print(e.eval(code))

        except Exception:
            log.exception('Evaluation error')
            continue

        except KeyboardInterrupt as ki:
            print(ki)
            continue

if __name__ == '__main__':
    repl()
