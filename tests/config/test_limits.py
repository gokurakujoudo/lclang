"""Unit tests mirroring :mod:`lclang.config.limits`."""

import pytest

from lclang.config import ConfigLoadLimits


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_load_limits_require_positive_integers(value: object) -> None:
    """Every resource ceiling shares strict positive-integer validation."""
    with pytest.raises(ValueError):
        ConfigLoadLimits(max_sources=value)  # type: ignore[arg-type]
