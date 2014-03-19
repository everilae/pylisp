# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

from functools import partial
from io import StringIO
import string


class Token(object):
    def __init__(self, value, lineno, linepos):
        self.value = value
        self.lineno = lineno
        self.linepos = linepos


class QUOTE(Token):
    pass


class COMMENT(Token):
    pass


class LPAR(Token):
    pass


class RPAR(Token):
    pass


class STRING(Token):
    pass


class SYMBOL(Token):
    pass


class Tokenizer(object):

    LISTOPS = {'(', ')'}
    OPS = LISTOPS.union({';', '\''})
    STRING = '"'
    NONSYMBOL = {'(', ')', ';'}
    WHITESPACE = frozenset(string.whitespace)

    _OP_LOOKUP = {
        '(': LPAR,
        ')': RPAR,
        ';': COMMENT,
        '\'': QUOTE,
    }

    def __init__(self, source):
        if isinstance(source, str):
            source = StringIO(source)

        self.source = source

        self._lineno = 1
        self._linepos = 0
        self._string = None
        self._symbol = None
        self._comment = None

    def _new(self, name):
        setattr(self, name, ([], self._lineno, self._linepos))

    def _flush(self, name, type_):
        attr = getattr(self, name)
        value = type_(''.join(attr[0]), attr[1], attr[2])
        setattr(self, name, None)
        return value

    def _new_symbol(self):
        self._new('_symbol')

    def _acc_symbol(self, chr_):
        if not self._symbol:
            self._new_symbol()

        self._symbol[0].append(chr_)

    def _flush_symbol(self):
        return self._flush('_symbol', SYMBOL)

    def _new_string(self):
        self._new('_string')

    def _acc_string(self, chr_):
        if self._string:
            self._string[0].append(chr_)

    def _flush_string(self):
        return self._flush('_string', STRING)

    def _new_comment(self):
        self._new('_comment')

    def _acc_comment(self, chr_):
        self._comment[0].append(chr_)

    def _flush_comment(self):
        return self._flush('_comment', COMMENT)

    def tokenize(self):
        for block in iter(partial(self.source.read, 512), ''):
            yield from self._next(block)

        # Final flush
        if self._comment:
            yield self._flush_comment()

        elif self._symbol:
            yield self._flush_symbol()

        elif self._string:
            raise SyntaxError("EOF while scanning string literal")

    def _next(self, block):
        for chr_ in block:
            self._linepos += 1

            if self._comment:
                self._acc_comment(chr_)

            elif chr_ == self.STRING:
                if self._string:
                    if not self._string[0][-1] == '\\':
                        yield self._flush_string()

                    else:
                        self._acc_string(chr_)

                else:
                    if self._symbol:
                        yield self._flush_symbol()

                    self._new_string()

            elif chr_ == '\n':
                if self._comment:
                    yield self._flush_comment()

                elif self._symbol:
                    yield self._flush_symbol()

                else:
                    self._acc_string(chr_)

                self._lineno += 1
                self._linepos = 0
                continue

            elif self._string:
                self._acc_string(chr_)

            elif chr_ in self.WHITESPACE:
                if self._symbol:
                    yield self._flush_symbol()

                continue

            elif chr_ in self.OPS:
                if self._symbol:
                    if chr_ in self.LISTOPS:
                        yield self._flush_symbol()

                    else:
                        self._acc_symbol(chr_)
                        continue

                yield self._OP_LOOKUP[chr_](chr_, self._lineno, self._linepos)

            else:
                self._acc_symbol(chr_)
