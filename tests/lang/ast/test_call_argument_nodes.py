"""Unit tests mirroring :mod:`lclang.lang.ast.call_argument_nodes`."""

import pytest

from lclang.common.identifiers import VarName
from lclang.error import LclValidationError
from lclang.lang.ast import LclConstant, LclName
from lclang.lang.ast.call_argument_nodes import (
    LclKeywordArgument,
    LclKeywordUnpackArgument,
    LclPositionalArgument,
    LclStarArgument,
)
from lclang.lang.ast.primary_nodes import LclCall


def test_call_children_preserve_receiver_then_arguments() -> None:
    """Calls retain explicit argument wrappers and source ordering."""
    function = LclName(identifier=VarName("function"))
    first = LclConstant(value=1)
    second = LclConstant(value=2)
    arguments = (
        LclPositionalArgument(first),
        LclStarArgument(second),
        LclKeywordArgument(VarName("key"), first),
        LclKeywordUnpackArgument(second),
    )
    call = LclCall(function, arguments)
    assert call.children() == (function, *arguments)
    assert tuple(argument.children() for argument in arguments) == (
        (first,),
        (second,),
        (first,),
        (second,),
    )


def test_keyword_argument_rejects_empty_name() -> None:
    """Explicit keyword arguments always have a usable identifier."""
    with pytest.raises(LclValidationError):
        LclKeywordArgument(VarName(""), LclConstant(value=None))
