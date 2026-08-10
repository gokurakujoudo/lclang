"""Reviewed fixed-point recursion helper for eager LCL functions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pylcl.lang.evaluator.awaitables import resolve_awaitable
from pylcl.lang.evaluator.functions import LclFunctionValue


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

    async def __call__(self, *args: object, **kwargs: object) -> object:
        """Build and invoke one fresh recursive step.

        :param args: Positional arguments forwarded to the produced function.
        :param kwargs: Named arguments forwarded to the produced function.
        :returns: Fully resolved result of the produced function.
        :raises TypeError: If the builder does not produce a callable.
        """
        function = await resolve_awaitable(self.builder(self))
        if not callable(function):
            raise TypeError("recursive builder must return a callable")
        return await resolve_awaitable(function(*args, **kwargs))


def recursive(builder: Callable[..., object]) -> RecursiveFunction:
    """Return the variadic eager fixed point of a function builder.

    :param builder: Callable accepting the delayed recursive operation and
       returning the function for one invocation step.
    :returns: Async callable supporting positional and named recursive calls.
    :raises TypeError: If *builder* or a function produced by it is not callable.

    .. note::
       Each invocation asks the builder for a fresh LCL closure. This is the
       Python equivalent of the variadic eager Z combinator and respects LCL's
       same-closure recursion guard.
    """
    if not callable(builder):
        raise TypeError("recursive builder must be callable")
    if isinstance(builder, LclFunctionValue):
        source = repr(builder)
    else:
        name = getattr(builder, "__name__", None)
        source = name if isinstance(name, str) else type(builder).__name__
    return RecursiveFunction(builder, source)
