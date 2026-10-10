"""Default-value declarations shared by workflow and CLI bindings."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.utilities import Code as utilities_codes


class DefaultOmission(Enum):
    """Identify omission independently of every caller-supplied value."""

    # Unitless declaration sentinel; identity, rather than None, distinguishes
    # omission so explicit null defaults keep their normal configuration meaning.
    ABSENT = "absent"


# Unitless shared sentinel selected from DefaultOmission for immutable API defaults.
NO_DEFAULT = DefaultOmission.ABSENT


@guard_constructor(LclValidationError, utilities_codes.NATIVE_781)
@dataclass(frozen=True, slots=True)
class DefaultBinding:
    """Describe a literal default or a lazily called no-argument factory.

    :param value: Fixed value retained by reference, or the omission sentinel.
    :param factory: Optional callable returning a value or awaitable.
    :raises LclValidationError: If both forms are supplied or the factory is not callable.
    """

    value: object = NO_DEFAULT
    factory: Callable[[], object] | None = None

    @guard_failure(LclValidationError, utilities_codes.NATIVE_781)
    def __post_init__(self) -> None:
        """Reject ambiguous or non-callable factory declarations.

        :raises LclValidationError: If both forms are supplied or the factory is not callable.
        """
        if self.factory is not None and (
            self.value is not NO_DEFAULT or not callable(self.factory)
        ):
            raise LclValidationError(
                "default and callable default_factory are mutually exclusive",
                code=utilities_codes.E81_DEFAULT_AND_CALLABLE_DEFAULT_FACTORY_ARE_MUTUALLY_EXCLUSIVE,
            )
