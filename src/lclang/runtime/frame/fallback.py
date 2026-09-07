"""Public sentinel controlling optional Frame lookup fallback behavior."""

from typing import Final

# Unique public sentinel preserving missing-name exceptions in Frame.get.
# Unitless singleton identity distinguishes omission of a get fallback from every supplied
# value, including None. One dedicated sentinel preserves the public missing-name contract.
NO_FALLBACK: Final[object] = object()
