"""Real public projection calls retain box payload and callback signatures."""

from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import Protocol, assert_type

from lclang.utils import CallableBox, ValueBox
from lclang.workflow import TaskProjection, define_variable


class Rule(Protocol):
    """An intentionally non-runtime-checkable keyword callback."""

    def __call__(self, text: str, *, upper: bool = False) -> str:
        """Transform one string."""
        ...


class OptionalRule(ValueBox[Rule | None]):
    """Give an optional callback a concrete nominal type."""


class NamedRule(ValueBox[Rule]):
    """Keep a Protocol's exact keyword contract through explicit delegation."""

    def __call__(self, text: str, *, upper: bool = False) -> str:
        """Delegate without erasing the keyword-only argument."""
        return self.value(text, upper=upper)


@dataclass
class Options:
    """Project concrete wrappers without requiring TypeForm."""

    rule: OptionalRule
    items: ValueBox[Collection[str]]
    convert: CallableBox[[str], int]
    path: str


def check_quote_types() -> None:
    """Mypy and Pyright check exact inferred results without casts or ignores."""
    source = define_variable[Options]("source")
    assert_type(source.field("rule", OptionalRule), TaskProjection[OptionalRule])
    assert_type(source.field("rule", OptionalRule).quote.value, Rule | None)
    assert_type(source.field("items", ValueBox[Collection[str]]).quote, ValueBox[Collection[str]])
    assert_type(source.field("convert", CallableBox[[str], int]).quote, CallableBox[[str], int])
    assert_type(source.field("path", str).quote, str)
    assert_type(define_variable[Rule]("rule").quote, Rule)
    assert_type(define_variable[str | None]("optional").quote, str | None)
    assert_type(define_variable[list[str]]("list").quote, list[str])
    assert_type(define_variable[Callable[[str], int]]("callback").quote, Callable[[str], int])


def test_callback_types() -> None:
    """ParamSpec keeps keywords and custom subclasses retain Protocol signatures."""

    def convert(text: str, *, upper: bool = False) -> str:
        return text.upper() if upper else text

    callback = CallableBox(convert)
    assert_type(callback("hello", upper=True), str)
    assert callback("hello", upper=True) == "HELLO"
    named = NamedRule(convert)
    assert_type(named("hello", upper=True), str)
    assert named("hello", upper=True) == "HELLO"
