"""Shared internal evaluator callback type aliases."""

from collections.abc import Awaitable, Callable

from pylcl.ast import LclAstNode
from pylcl.lang.evaluator.context import Resolver

type EvaluateNode = Callable[[LclAstNode, Resolver], Awaitable[object]]
