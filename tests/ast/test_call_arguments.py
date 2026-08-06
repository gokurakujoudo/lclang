"""Unit tests mirroring :mod:`pylcl.ast.call_arguments`."""

import pytest

from pylcl.ast import LclConstant, LclName
from pylcl.ast.call_arguments import (
    LclKeywordArgument,
    LclKeywordUnpackArgument,
    LclPositionalArgument,
    LclStarArgument,
)
from pylcl.ast.primaries import LclCall
from pylcl.types import VarName


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
    with pytest.raises(ValueError):
        LclKeywordArgument(VarName(""), LclConstant(value=None))
