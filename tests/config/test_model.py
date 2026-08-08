"""Unit tests mirroring :mod:`pylcl.config.model`."""

import pytest

from pylcl.ast import LclConstant
from pylcl.config import ConfigDefinition, ConfigDocument, ConfigUsing
from pylcl.source import SourceOrigin, SourcePosition, SourceSpan
from pylcl.types import SourceName, VarName
from tests.config.support import source_span


def test_model_values_reject_invalid_scalar_and_origin_state() -> None:
    """All immutable declaration and document invariants reject bad construction."""
    span = source_span()
    expression = LclConstant(1, span=span)
    with pytest.raises(ValueError):
        ConfigDefinition(VarName(""), expression, span, 0)
    with pytest.raises(ValueError):
        ConfigDefinition(VarName("value"), expression, span, -1)
    with pytest.raises(ValueError):
        ConfigUsing("", span, 0)
    with pytest.raises(ValueError):
        ConfigUsing("child.lclcfg", span, -1)
    with pytest.raises(ValueError):
        ConfigDocument(span.origin, 0, ())
    declaration = ConfigDefinition(VarName("value"), expression, span, 1)
    with pytest.raises(ValueError):
        ConfigDocument(span.origin, 1, (declaration,))
    other = SourceOrigin(SourceName("other"))
    other_span = SourceSpan(other, SourcePosition(1, 1, 0), SourcePosition(1, 2, 1))
    declaration = ConfigDefinition(VarName("value"), expression, other_span, 0)
    with pytest.raises(ValueError):
        ConfigDocument(span.origin, 1, (declaration,))
