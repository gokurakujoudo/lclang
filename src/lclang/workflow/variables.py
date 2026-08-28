"""Typed variables used by workflow dataclass mappings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from lclang.scopes import validate_qualified_name


@dataclass(frozen=True, slots=True)
class TaskVar[ValueT]:
    """Describe one named value crossing workflow task boundaries.

    :param name: Valid qualified LCL binding name.
    :param description: Human-readable help text.
    :param is_masked: Whether lclang-owned diagnostics redact the value.
    :param value_type: Python type retained for CLI documentation.
    """

    name: str
    description: str
    is_masked: bool
    value_type: object

    @property
    def quote(self) -> ValueT:
        """Return this mapping marker with its declared value type.

        :returns: This variable cast to the mapped field type.
        """
        return cast(ValueT, self)


class VariableDefinition:
    """Provide subscription syntax for typed workflow variables."""

    def __getitem__[ValueT](self, value_type: type[ValueT]) -> Callable[..., TaskVar[ValueT]]:
        """Return a constructor retaining one runtime value type.

        :param value_type: Python type represented by the variable.
        :returns: Typed variable constructor.
        :raises TypeError: If subscription does not receive a type-like value.
        """

        def construct(
            name: str,
            description: str = "",
            is_masked: bool = False,
        ) -> TaskVar[ValueT]:
            """Create one validated workflow variable.

            :param name: Qualified LCL binding name.
            :param description: Human-readable help text.
            :param is_masked: Whether diagnostics redact this value.
            :returns: Immutable typed workflow variable.
            :raises TypeError: If metadata has an incompatible type.
            :raises ValueError: If *name* is not a qualified LCL name.
            """
            validate_qualified_name(name)
            if not isinstance(description, str):
                raise TypeError("workflow variable description must be text")
            if not isinstance(is_masked, bool):
                raise TypeError("workflow variable masked flag must be Boolean")
            return TaskVar(name, " ".join(description.split()), is_masked, value_type)

        return construct


# Shared stateless typed-variable factory.
define_variable = VariableDefinition()
