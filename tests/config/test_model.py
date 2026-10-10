"""Unit tests mirroring :mod:`lclang.config.config_document`."""

import pytest

from lclang.common.identifiers import SourceName, VarName
from lclang.common.source_location import SourceOrigin, SourcePosition, SourceSpan
from lclang.config import ConfigDefinition, ConfigDocument, ConfigUsing
from lclang.error import LclValidationError
from lclang.lang.ast import LclConstant
from tests.config.support import source_span


def test_model_values_reject_invalid_scalar_and_origin_state() -> None:
    """All immutable declaration and document invariants reject bad construction."""
    span = source_span()
    expression = LclConstant(1, span=span)
    with pytest.raises(LclValidationError):
        ConfigDefinition(VarName(""), expression, span, 0)
    with pytest.raises(LclValidationError):
        ConfigDefinition(VarName("value"), expression, span, -1)
    with pytest.raises(LclValidationError):
        ConfigDefinition(VarName("value"), expression, span, 0, 1)  # type: ignore[arg-type]
    with pytest.raises(LclValidationError):
        ConfigUsing("", span, 0)
    with pytest.raises(LclValidationError):
        ConfigUsing(expression, span, 0)  # type: ignore[arg-type]
    with pytest.raises(LclValidationError):
        ConfigUsing("child.lclcfg", span, -1)
    assert ConfigUsing("child.lclcfg", span, 0).optional is False
    assert ConfigUsing("child.lclcfg", span, 0, True).optional is True
    with pytest.raises(LclValidationError, match="optional"):
        ConfigUsing("child.lclcfg", span, 0, 1)  # type: ignore[arg-type]
    with pytest.raises(LclValidationError):
        ConfigDocument(span.origin, 0, ())
    declaration = ConfigDefinition(VarName("value"), expression, span, 1)
    with pytest.raises(LclValidationError):
        ConfigDocument(span.origin, 1, (declaration,))
    other = SourceOrigin(SourceName("other"))
    other_span = SourceSpan(other, SourcePosition(1, 1, 0), SourcePosition(1, 2, 1))
    declaration = ConfigDefinition(VarName("value"), expression, other_span, 0)
    with pytest.raises(LclValidationError):
        ConfigDocument(span.origin, 1, (declaration,))
