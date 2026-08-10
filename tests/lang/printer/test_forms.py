"""Unit tests mirroring :mod:`lclang.lang.printer.forms`."""

import pytest

from lclang.lang.parser import parse_expression
from lclang.lang.printer import to_source


@pytest.mark.parametrize(
    ("source", "canonical"),
    [
        (
            "(x,y=1,*args,option=2,**kwargs)->x+y",
            "(x, y=1, *args, option=2, **kwargs) -> x + y",
        ),
        ("x->x", "(x) -> x"),
        ("()->1", "() -> 1"),
        ("x->y->x+y", "(x) -> (y) -> x + y"),
        ("raise(Error('x'))", "raise(Error('x'))"),
        ("assert(value,'bad')", "assert(value, 'bad')"),
        (
            "try:value except Error as error:recover(error) finally:cleanup()",
            "try: value except Error as error: recover(error) finally: cleanup()",
        ),
        ("try:value except Error:recover()", "try: value except Error: recover()"),
        ("try:value except:recover()", "try: value except: recover()"),
        ("with lock() as lock,file():value", "with lock() as lock, file(): value"),
        ("with lock():value", "with lock(): value"),
    ],
)
def test_form_source_is_canonical(source: str, canonical: str) -> None:
    """Function, error, and control forms print with unambiguous boundaries."""
    printed = to_source(parse_expression(source))
    assert printed == canonical
    assert to_source(parse_expression(printed)) == canonical
