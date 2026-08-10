"""Shared internal evaluator callback type aliases."""

from collections.abc import Awaitable, Callable

from lclang.ast import LclAstNode
from lclang.lang.evaluator.context import Resolver

type EvaluateNode = Callable[[LclAstNode, Resolver], Awaitable[object]]
