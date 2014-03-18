pylisp
======

Silly Python Lisp interpreter that runs on Python 3.

Usage
=====

    # To run a rudimentary Read-Eval-Print-Loop
    python3 -m pylisp.repl
    
    # Tests
    python3 -m pylisp.tests

What "Works"
============

Not much.

```lisp
python3 -m pylis.repl
Silly Python Lisp 0 on Linux
>>> (define factorial (lambda (x) (if (<= x 0) 1 (* x (factorial (- x 1))))))
None
>>> (factorial 30)
265252859812191058636308480000000
>>> ; Recursion depth is really really shallow at the moment, values like 70 will crash
```
