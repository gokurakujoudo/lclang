"""Shared internal callable and result types for renderer modules."""

from collections.abc import Callable

from pylcl.ast import LclAstNode

type Render = Callable[[LclAstNode, int], str]
type RenderResult = tuple[str, int]
