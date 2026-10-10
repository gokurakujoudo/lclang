"""Shared internal evaluator callback type aliases.

This package groups the implementation modules listed in its directory.
"""

from collections.abc import Awaitable, Callable

from lclang.lang.ast import LclAstNode
from lclang.lang.engine.evaluator.name_resolver import Resolver

type EvaluateNode = Callable[[LclAstNode, Resolver], Awaitable[object]]
