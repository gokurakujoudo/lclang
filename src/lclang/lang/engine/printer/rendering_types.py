"""Shared internal callable and result types for renderer modules.

This package groups the implementation modules listed in its directory.
"""

from collections.abc import Callable

from lclang.lang.ast import LclAstNode

type Render = Callable[[LclAstNode, int], str]
type RenderResult = tuple[str, int]
