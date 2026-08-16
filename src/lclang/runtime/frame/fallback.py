"""Public sentinel controlling optional Frame lookup fallback behavior."""

from typing import Final

# Unique public sentinel preserving missing-name exceptions in Frame.get.
NO_FALLBACK: Final[object] = object()
