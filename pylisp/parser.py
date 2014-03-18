# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import logging
from .utils import MethodDict
from . import ir
from io import StringIO
import string


class Parser(object):

    _log = logging.getLogger('Parser')

    parsers = MethodDict()

    def __init__(self, source):
        self.source = source
        self.ir = [ir.Package()]

        self._line = None
        self._lineno = None
        self._linepos = None

        if isinstance(self.source, str):
            self.source = StringIO(self.source)

    def parse(self):
        self._log.debug('parsing %r', self.source)

        for lineno, line in enumerate(self.source, 1):
            self._line = line
            self._lineno = lineno
            self._linepos = 0
            self._linelen = len(line)
            # Start parsing for this line
            while self._linepos < self._linelen:
                self._parse()

        if not isinstance(self.ir[-1], ir.Package):
            raise self._syntax_error("unexpected EOF")

        return self.ir[-1]

    def _parse(self):
        chr_ = self._line[self._linepos]

        while  chr_ in string.whitespace:
            self._linepos += 1

            if self._linepos >= self._linelen:
                # Line ended with whitespace
                return

            chr_ = self._line[self._linepos]
            continue

        self.parsers.get(chr_, Parser.create_symbol)(self)

    def _syntax_error(self, msg):
        return SyntaxError('{}, line {} col {}'.format(
            msg, self._lineno, self._linepos))

    def _pop_quote(self):
        if getattr(self.ir[-1], 'is_quote', False):
            self.ir.pop()

    @parsers.annotate(';')
    def comment(self):
        self._linepos = self._linelen

    @parsers.annotate("'")
    def quote(self):
        quote = ir.Symbol('quote', lineno=self._lineno,
                          col_offset=self._linepos)
        self.begin_list(quote=True)
        self.ir[-1].append(quote)

    @parsers.annotate('(')
    def begin_list(self, quote=False):
        list_ = ir.List(lineno=self._lineno, col_offset=self._linepos)
        setattr(list_, 'is_quote', quote)
        self.ir[-1].append(list_)
        self.ir.append(list_)
        self._linepos += 1

    @parsers.annotate(')')
    def end_list(self):
        if not isinstance(self.ir[-1], ir.List):
            raise self._syntax_error('unexpected end of list')

        self.ir.pop()
        self._pop_quote()
        self._linepos += 1

    @parsers.annotate('"')
    def create_str(self):
        done = False
        start = self._linepos + 1
        end = self._line.find('"', start)

        while not done and end < self._linelen:
            if end == -1:
                raise self._syntax_error('unterminated string')

            if self._line[end - 1] != '\\':
                done = True

            else:
                end = self._line.find('"', end + 1)

        s = ir.Str(self._line[start:end], lineno=self._lineno,
                   col_offset=self._linepos)
        self.ir[-1].append(s)
        self._pop_quote()
        self._linepos = end + 1

    def create_symbol(self):
        start = self._linepos
        end = start
        non_symbol_chrs = frozenset(string.whitespace + ')')

        while end < self._linelen and self._line[end] not in non_symbol_chrs:
            end += 1

        value = self._line[start:end]

        try:
            try:
                value = int(value)

            except ValueError:
                value = float(value)

            symbol = ir.Number

        except ValueError:
            symbol = ir.Symbol

        self.ir[-1].append(symbol(value, lineno=self._lineno,
                                  col_offset=self._linepos))
        self._pop_quote()
        self._linepos = end
