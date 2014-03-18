pylisp
======

Silly Python Lisp interpreter that runs on Python 3.

Usage
=====

```bash
# To run a rudimentary Read-Eval-Print-Loop
python3 -m pylisp.repl

# Tests
python3 -m pylisp.tests
```

What "Works"
============

Not much.

```lisp
Silly Python Lisp 0 on Linux
>>> ; Recursion depth is really really shallow at the moment, values like 70 will crash
None
>>> (define factorial (lambda (x) (if (<= x 0) 1 (* x (factorial (- x 1))))))
None
>>> (factorial 30)
265252859812191058636308480000000
>>> ; Calling python builtins is possible with a twist
None
>>> (print (str.upper "hello, world!"))
HELLO, WORLD!
```
