"""Resource ceilings for recursive configuration loading."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigLoadLimits:
    """Bound source loading and expansion work.

    :param max_sources: Maximum distinct requested source paths.
    :param max_depth: Maximum recursive using depth including the root.
    :param max_characters: Maximum decoded characters across unique sources.
    :param max_declarations: Maximum declarations across unique sources.
    :raises ValueError: If any ceiling is not a positive integer.

    .. note::
       Counts cover unique parsed sources while expansion placement may repeat.
    """

    max_sources: int = 1_000
    max_depth: int = 100
    max_characters: int = 10_000_000
    max_declarations: int = 100_000

    def __post_init__(self) -> None:
        """Reject booleans, non-integers, and non-positive ceilings.

        :returns: ``None``.
        :raises ValueError: If any ceiling is not a positive integer.

        .. note::
           Booleans are excluded despite inheriting from :class:`int`.
        """
        values = (
            self.max_sources,
            self.max_depth,
            self.max_characters,
            self.max_declarations,
        )
        if any(type(value) is not int or value <= 0 for value in values):
            raise ValueError("config load limits must be positive integers")
