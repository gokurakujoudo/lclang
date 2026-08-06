"""Unit tests mirroring :mod:`pylcl.lang.printer.forms`."""

import pytest

from pylcl.lang.parser import parse_expression
from pylcl.lang.printer import to_source


@pytest.mark.parametrize(
    ("source", "canonical"),
    [
        (
            "def(x,y=1,*args,option=2,**kwargs):x+y",
            "def (x, y=1, *args, option=2, **kwargs): x + y",
        ),
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
    assert to_source(parse_expression(source)) == canonical
