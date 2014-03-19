# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import logging
from .utils import MethodDict
from .tokenizer import Tokenizer, LPAR, RPAR, STRING, SYMBOL, QUOTE, COMMENT
from . import ir


class Parser(object):

    _log = logging.getLogger('Parser')

    parsers = MethodDict()

    def __init__(self, source):
        self.source = source
        self.ir = [ir.Package()]
        self.tokenizer = Tokenizer(self.source)

    def parse(self):
        self._log.debug('parsing %r', self.source)

        for token in self.tokenizer.tokenize():
            parser = self.parsers.get(type(token))

            if parser is None:
                raise ValueError('unexpected token {!r}'.format(token))

            parser(self, token)

        if not isinstance(self.ir[-1], ir.Package):
            raise SyntaxError("unexpected EOF")

        return self.ir[-1]

    def _pop_quote(self):
        if getattr(self.ir[-1], 'is_quote', False):
            sexpr = self.ir.pop()
            self.ir[-1].append(sexpr.head)

    @parsers.annotate(QUOTE)
    def quote(self, token):
        quote = ir.Symbol('quote', lineno=token.lineno,
                          col_offset=token.linepos)
        self.begin_list(token, quote=True)
        self.ir[-1].append(quote)

    @parsers.annotate(LPAR)
    def begin_list(self, token, quote=False):
        list_ = ir.SExpr(lineno=token.lineno, col_offset=token.linepos)
        setattr(list_, 'is_quote', quote)
        self.ir.append(list_)

    @parsers.annotate(RPAR)
    def end_list(self, token):
        if not isinstance(self.ir[-1], ir.SExpr):
            raise SyntaxError('unexpected end of list')

        sexpr = self.ir.pop()
        # Push cons to intermediate results
        self.ir[-1].append(sexpr.head)
        self._pop_quote()

    @parsers.annotate(STRING)
    def create_str(self, token):
        s = ir.Str(token.value, lineno=token.lineno,
                   col_offset=token.linepos)
        self.ir[-1].append(s)
        self._pop_quote()

    @parsers.annotate(SYMBOL)
    def create_symbol(self, token):
        value = token.value

        try:
            try:
                value = int(value)

            except ValueError:
                value = float(value)

            symbol = ir.Number

        except ValueError:
            symbol = ir.Symbol

        self.ir[-1].append(symbol(value, lineno=token.lineno,
                                  col_offset=token.linepos))
        self._pop_quote()

    @parsers.annotate(COMMENT)
    def create_comment(self, token):
        """
        Ignore comments
        """
        pass
