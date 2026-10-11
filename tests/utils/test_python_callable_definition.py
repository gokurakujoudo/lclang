"""Callable metadata comes from code and never evaluates host properties."""

from collections.abc import Callable
from functools import partial, wraps
from types import FunctionType, MethodType
from typing import Any, cast

import pytest

from lclang.error import LclValidationError
from lclang.error.diagnostic_records import DiagnosticValue, EvaluationContextFrame
from lclang.lang.common.source_location import UNKNOWN_SPAN
from lclang.utils import PythonCallableDefinition
from lclang.utils.python_callable_definition import describe_python_callable, render_python_callable


def identity(value: object) -> object:
    """Return an argument for metadata examples."""
    return value


class Host:
    """Expose ordinary and static invocation metadata."""

    def method(self, value: object) -> object:
        return value

    def __call__(self, value: object) -> object:
        return value


class StaticHost:
    """Supply a static descriptor as the actual implementation."""

    __call__ = staticmethod(identity)


class ClassHost:
    """Supply a class method descriptor as the actual implementation."""

    @classmethod
    def __call__(cls, value: object) -> object:
        return value


@pytest.mark.parametrize(
    "value, expected",
    [
        (identity, identity),
        (partial(identity, 1), identity),
        (Host().method, Host.method),
        (Host(), Host.__call__),
        (StaticHost(), identity),
        (ClassHost(), cast(MethodType, ClassHost.__call__).__func__),
    ],
)
def test_known_callable_variants_report_actual_code(value: object, expected: object) -> None:
    """Code filename and first line remain the implementation's original metadata."""
    definition = describe_python_callable(value)
    function = cast(Any, expected)
    assert definition == PythonCallableDefinition(
        function.__code__.co_qualname,
        function.__code__.co_filename,
        function.__code__.co_firstlineno,
    )
    assert render_python_callable(value) is not None
    assert "0x" not in cast(str, render_python_callable(value))


def test_decorators_keep_the_wrapper_location_and_synthetic_names() -> None:
    """A published wrapped name does not replace actual executing code metadata."""

    @wraps(identity)
    def wrapper(value: object) -> object:
        return identity(value)

    definition = describe_python_callable(wrapper)
    assert (
        definition is not None
        and definition.line == cast(FunctionType, wrapper).__code__.co_firstlineno
    )
    assert definition.qualified_name.endswith(".<locals>.wrapper")
    synthetic = identity.__code__.replace(co_filename="<application-generated>")
    generated = FunctionType(synthetic, identity.__globals__)
    assert describe_python_callable(generated) == PythonCallableDefinition(
        synthetic.co_qualname, "<application-generated>", synthetic.co_firstlineno
    )


def test_builtin_and_unknown_callables_have_no_invented_source() -> None:
    """Native implementations and non-callables retain honest source absence."""
    assert describe_python_callable(len) is None
    assert render_python_callable(len) == "Python callable len"
    assert describe_python_callable(3) is None and render_python_callable(3) is None

    class PropertyHost:
        @property
        def __call__(self) -> object:
            raise AssertionError("must not access this property")

    assert describe_python_callable(PropertyHost()) is None
    assert "PropertyHost" in cast(str, render_python_callable(PropertyHost()))

    class SneakyPartial(partial[object]):
        @property
        def func(self) -> Callable[..., object]:
            raise AssertionError("must not access overridden func")

    assert describe_python_callable(SneakyPartial(identity)) == describe_python_callable(identity)


@pytest.mark.parametrize(
    "fields, code",
    [
        (("", "app.py", 1), "LCL831212"),
        (("callback", "", 1), "LCL831212"),
        ((1, "app.py", 1), "LCL831212"),
        (("callback", "app.py", 0), "LCL831221"),
        (("callback", "app.py", True), "LCL831221"),
        (("callback", "app.py", "1"), "LCL831221"),
    ],
)
def test_invalid_metadata_is_a_coded_failure(fields: tuple[object, ...], code: str) -> None:
    """Constructor input validation remains meaningful for untyped applications."""
    with pytest.raises(LclValidationError) as caught:
        PythonCallableDefinition(*cast(Any, fields))
    assert caught.value.code == code


@pytest.mark.parametrize(
    "changes", [{"co_filename": ""}, {"co_firstlineno": 0}, {"co_qualname": ""}]
)
def test_unavailable_code_metadata_does_not_reject_the_callable(changes: dict[str, object]) -> None:
    """Generated functions still run when their definition cannot be located."""
    code = identity.__code__.replace(**cast(Any, changes))
    generated = FunctionType(code, identity.__globals__)
    assert generated(39) == 39
    assert describe_python_callable(generated) is None
    assert render_python_callable(generated) == "Python callable function"


def test_diagnostic_records_validate_optional_metadata() -> None:
    """Old constructors still work; new optional records have a typed contract."""
    definition = describe_python_callable(identity)
    value = DiagnosticValue(
        "fn", UNKNOWN_SPAN, "function", "identity", callable_definition=definition
    )
    frame = EvaluationContextFrame(
        "fn", UNKNOWN_SPAN, "fn()", kind="python-call", callable_definition=definition
    )
    assert value.callable_definition is definition and frame.callable_definition is definition
    with pytest.raises(LclValidationError) as caught:
        DiagnosticValue(
            "fn", UNKNOWN_SPAN, "function", "identity", callable_definition=cast(Any, 1)
        )
    assert caught.value.code == "LCL831192"
    with pytest.raises(LclValidationError):
        EvaluationContextFrame("fn", UNKNOWN_SPAN, "fn()", callable_definition=cast(Any, 1))
