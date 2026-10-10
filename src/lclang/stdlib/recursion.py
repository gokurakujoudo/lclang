"""Reviewed fixed-point recursion helper for eager LCL functions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lclang.error import LclStandardError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_constructor, guard_failure
from lclang.error.codes.standard import Code as standard_codes
from lclang.lang.evaluator.awaitables import resolve_awaitable
from lclang.lang.evaluator.functions import LclFunctionValue


@guard_constructor(LclValidationError, standard_codes.NATIVE_971)
@dataclass(frozen=True, slots=True)
class RecursiveFunction:
    """Represent one callable eager fixed point with stable source identity.

    :param builder: Callable producing a fresh function for each recursive step.
    :param source: Canonical LCL builder source or Python builder function name.
    """

    builder: Callable[..., object]
    source: str

    def __repr__(self) -> str:
        """Return the stable source-oriented recursive function representation.

        :returns: Recursive function label followed by its builder source or name.
        """
        return f"Recursive Function: {self.source}"

    @guard_async_failure(LclStandardError, standard_codes.NATIVE_971)
    async def __call__(self, *args: object, **kwargs: object) -> object:
        """Build and invoke one fresh recursive step.

        :param args: Positional arguments forwarded to the produced function.
        :param kwargs: Named arguments forwarded to the produced function.
        :returns: Fully resolved result of the produced function.
        :raises LclValidationError: If the builder does not produce a callable.
        """
        function = await resolve_awaitable(self.builder(self))
        if not callable(function):
            raise LclValidationError(
                "recursive builder must return a callable",
                code=standard_codes.E71_RECURSIVE_BUILDER_MUST_RETURN_A_CALLABLE,
            )
        return await resolve_awaitable(function(*args, **kwargs))


@guard_failure(LclStandardError, standard_codes.NATIVE_971)
def recursive(builder: Callable[..., object]) -> RecursiveFunction:
    """Return the variadic eager fixed point of a function builder.

    :param builder: Callable accepting the delayed recursive operation and
       returning the function for one invocation step.
    :returns: Async callable supporting positional and named recursive calls.
    :raises LclValidationError: If *builder* or a function produced by it is not callable.

    .. note::
       Each invocation asks the builder for a fresh LCL closure. This is the
       Python equivalent of the variadic eager Z combinator and respects LCL's
       same-closure recursion guard.
    """
    if not callable(builder):
        raise LclValidationError(
            "recursive builder must be callable",
            code=standard_codes.E71_RECURSIVE_BUILDER_MUST_BE_CALLABLE,
        )
    if isinstance(builder, LclFunctionValue):
        source = repr(builder)
    else:
        name = getattr(builder, "__name__", None)
        source = name if isinstance(name, str) else type(builder).__name__
    return RecursiveFunction(builder, source)
