"""Default-value declarations shared by workflow and CLI bindings."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class DefaultOmission(Enum):
    """Identify omission independently of every caller-supplied value."""

    # Unitless declaration sentinel; identity, rather than None, distinguishes
    # omission so explicit null defaults keep their normal configuration meaning.
    ABSENT = "absent"


# Unitless shared sentinel selected from DefaultOmission for immutable API defaults.
NO_DEFAULT = DefaultOmission.ABSENT


@dataclass(frozen=True, slots=True)
class DefaultBinding:
    """Describe a literal default or a lazily called no-argument factory.

    :param value: Fixed value retained by reference, or the omission sentinel.
    :param factory: Optional callable returning a value or awaitable.
    :raises TypeError: If both forms are supplied or the factory is not callable.
    """

    value: object = NO_DEFAULT
    factory: Callable[[], object] | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous or non-callable factory declarations.

        :raises TypeError: If both forms are supplied or the factory is not callable.
        """
        if self.factory is not None and (
            self.value is not NO_DEFAULT or not callable(self.factory)
        ):
            raise TypeError("default and callable default_factory are mutually exclusive")
