"""Typed guards for native failures at public operation boundaries."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, cast

from lclang.error.base import LclError, LclFrozenAttributeError, LclValidationError
from lclang.error.codes.general import Code as general_codes
from lclang.error.wrapping import is_ordinary_failure, wrap_failure


def wrap_boundary_failure(error: Exception, error_type: type[LclError], code: str) -> LclError:
    """Distinguish rejected call arguments from failures inside an operation.

    :param error: Native failure captured by a function call guard.
    :param error_type: Family selected for failures after entering the operation.
    :param code: Registered operation code for failures after entry.
    :returns: Structured failure retaining the original native exception.
    """
    trace = error.__traceback__
    if isinstance(error, TypeError) and trace is not None and trace.tb_next is None:
        return wrap_failure(error, LclValidationError, general_codes.CALL_SIGNATURE)
    return wrap_failure(error, error_type, code)


def guard_failure[**Params, Result](
    error_type: type[LclError], code: str
) -> Callable[[Callable[Params, Result]], Callable[Params, Result]]:
    """Preserve a synchronous signature while classifying escaping native failures.

    :param error_type: Failure family selected by the operation owner.
    :param code: Registered native-operation code for that boundary.
    :returns: Decorator preserving existing LCL failures and process-control signals.
    """

    def decorate(function: Callable[Params, Result]) -> Callable[Params, Result]:
        """Wrap one operation without executing it during decoration.

        :param function: Original synchronous operation.
        :returns: Signature-preserving native-failure boundary.
        """

        @wraps(function)
        def call_operation(*args: Params.args, **kwargs: Params.kwargs) -> Result:
            """Call once, retaining ordinary causes and Python attribute signals.

            :param args: Original positional arguments.
            :param kwargs: Original keyword arguments.
            :returns: Original operation result.
            :raises LclError: If the operation fails ordinarily.
            """
            try:
                return function(*args, **kwargs)
            except Exception as error:
                if isinstance(error, LclError) or not is_ordinary_failure(error):
                    raise
                failure = wrap_boundary_failure(error, error_type, code)
                failure.add_note(f"lclang operation {function.__qualname__}")
                raise failure from error

        return call_operation

    return decorate


def guard_constructor[Class: type[object]](
    error_type: type[LclError], code: str
) -> Callable[[Class], Class]:
    """Guard the constructor of a class without replacing its class.

    :param error_type: Failure family for invalid constructor calls.
    :param code: Registered constructor boundary identifier.
    :returns: Class decorator preserving identity, fields, and the original signature.
    """

    def decorate(value: Class) -> Class:
        """Attach the same typed call guard used by ordinary public functions.

        :param value: Class with its original constructor.
        :returns: Original class with a guarded constructor.
        """
        constructor = cast(Callable[..., None], value.__init__)
        setattr(value, "__init__", guard_failure(error_type, code)(constructor))  # noqa: B010
        if getattr(getattr(value, "__dataclass_params__", None), "frozen", False):
            for name in ("__setattr__", "__delattr__"):
                mutation = cast(Callable[..., None], getattr(value, name))
                setattr(
                    value,
                    name,
                    guard_failure(LclFrozenAttributeError, general_codes.FROZEN_ATTRIBUTE)(
                        mutation
                    ),
                )
        return value

    return decorate


def guard_async_failure[Function: Callable[..., Coroutine[Any, Any, object]]](
    error_type: type[LclError], code: str
) -> Callable[[Function], Function]:
    """Preserve an async function's exact callable type and native coroutine signature.

    :param error_type: Failure family selected by the operation owner.
    :param code: Registered native-operation code for that boundary.
    :returns: Decorator retaining result types, cancellation, and existing diagnostics.
    """

    def decorate(function: Function) -> Function:
        """Wrap one awaited operation without creating background tasks.

        :param function: Original async function, including its parameter and result types.
        :returns: Wrapper with the original callable contract.
        """

        @wraps(function)
        async def await_operation(*args: object, **kwargs: object) -> object:
            """Await once and preserve the original failure as a cause.

            :param args: Original positional arguments.
            :param kwargs: Original keyword arguments.
            :returns: Awaited operation result.
            :raises LclError: If the operation fails ordinarily.
            """
            try:
                return await function(*args, **kwargs)
            except Exception as error:
                if isinstance(error, LclError) or not is_ordinary_failure(error):
                    raise
                failure = wrap_boundary_failure(error, error_type, code)
                failure.add_note(f"lclang operation {function.__qualname__}")
                raise failure from error

        # Both checkers keep the original async signature; wraps retains it at runtime.
        return cast(Function, await_operation)

    return decorate
