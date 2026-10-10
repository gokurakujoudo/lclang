"""Ordered evaluation and expansion of call argument wrappers.

Defines ``internal_evaluate_call``, ``internal_check_duplicate``,
``internal_merge_keywords``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

from lclang.error import LanguageErrorCode, LclEvaluationError
from lclang.lang.ast import (
    LclCall,
    LclKeywordArgument,
    LclKeywordUnpackArgument,
    LclPositionalArgument,
    LclStarArgument,
)
from lclang.lang.engine.evaluator.evaluation_callback import EvaluateNode
from lclang.lang.engine.evaluator.name_resolver import Resolver
from lclang.lang.engine.evaluator.value_iteration import iterate_values


async def internal_evaluate_call(
    node: LclCall,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Evaluate a call target and its arguments in source order.

    :param node: Call AST node containing the target and argument wrappers.
    :param resolver: Resolver used for every nested argument evaluation.
    :param evaluate: Recursive evaluator for nested AST expressions.
    :returns: Result returned by invoking the evaluated target.
    :raises LclEvaluationError: If an argument has an unsupported AST wrapper type.

    .. note::
       Starred positional values and keyword mappings are expanded only after
       their expressions are evaluated, preserving left-to-right semantics.
    """
    target = await evaluate(node.function, resolver)
    positional: list[object] = []
    keywords: dict[str, object] = {}
    for argument in node.arguments:
        if isinstance(argument, LclPositionalArgument):
            positional.append(await evaluate(argument.value, resolver))
        elif isinstance(argument, LclStarArgument):
            value = await evaluate(argument.value, resolver)
            positional.extend([item async for item in iterate_values(value)])
        elif isinstance(argument, LclKeywordArgument):
            name = str(argument.name)
            internal_check_duplicate(name, keywords)
            keywords[name] = await evaluate(argument.value, resolver)
        elif isinstance(argument, LclKeywordUnpackArgument):
            value = await evaluate(argument.value, resolver)
            internal_merge_keywords(value, keywords)
        else:
            raise LclEvaluationError(
                "unsupported call argument", code=LanguageErrorCode.E32_UNSUPPORTED_CALL_ARGUMENT
            )
    return cast(Callable[..., object], target)(*positional, **keywords)


def internal_check_duplicate(name: str, keywords: dict[str, object]) -> None:
    """Reject a keyword name that has already been collected.

    :param name: Keyword name about to be inserted.
    :param keywords: Mutable keyword accumulator for the current call.
    :returns: ``None``.
    :raises LclEvaluationError: If *name* is already present in *keywords*.

    .. note::
       Checking occurs before evaluating or inserting the associated value, so
       duplicate syntax cannot trigger an unnecessary value evaluation.
    """
    if name in keywords:
        raise LclEvaluationError(
            f"duplicate keyword argument: {name}",
            code=LanguageErrorCode.E32_DUPLICATE_KEYWORD_ARGUMENT,
        )


def internal_merge_keywords(value: object, keywords: dict[str, object]) -> None:
    """Merge one keyword-unpacking value into the call accumulator.

    :param value: Candidate mapping produced by a keyword-unpacking expression.
    :param keywords: Mutable keyword accumulator for the current call.
    :returns: ``None``.
    :raises LclEvaluationError: If *value* is not a mapping, contains a non-string key,
       or repeats a keyword already accumulated.

    .. note::
       Entries are validated and inserted in the mapping's iteration order,
       matching the language's left-to-right call assembly rules.
    """
    if not isinstance(value, Mapping):
        raise LclEvaluationError(
            "keyword unpacking requires a mapping",
            code=LanguageErrorCode.E32_KEYWORD_UNPACKING_REQUIRES_A_MAPPING,
        )
    for key, item in cast(Mapping[object, object], value).items():
        if not isinstance(key, str):
            raise LclEvaluationError(
                "keyword unpacking requires string keys",
                code=LanguageErrorCode.E32_KEYWORD_UNPACKING_REQUIRES_STRING_KEYS,
            )
        internal_check_duplicate(key, keywords)
        keywords[key] = item
