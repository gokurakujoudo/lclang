"""Report-local evidence ownership and exception-group common prefixes.

Defines ``DiagnosticEvidence``, ``find_shared_evaluation_prefix``, ``match_evaluation_frame``.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from lclang.lang.common.source_location import SourceSnapshot, SourceSpan

from lclang.error.diagnostic_records import EvaluationContextFrame
from lclang.error.exception_base import LclError

# Unitless immutable source keys retain physical evidence without runtime source imports.
type SourceBodyKey = tuple[int | str, SourceSpan, SourceSnapshot | None]


@dataclass(slots=True)
class DiagnosticEvidence:
    """Own expanded evaluation snapshots for one rendering operation.

    :param evaluations: Protected frame sequences already expanded in this report.
    :param sources: Source bodies already shown for each correlated failure.
    """

    evaluations: list[tuple[tuple[EvaluationContextFrame, ...], bool]] = field(
        default_factory=list[tuple[tuple[EvaluationContextFrame, ...], bool]]
    )
    sources: set[SourceBodyKey] = field(default_factory=set[SourceBodyKey])

    def claim_source(self, error: LclError) -> bool:
        """Reserve a body without hiding a separate failure at the same location.

        :param error: Original source owner and optional failure correlation.
        :returns: Whether the body has not been shown for this failure.
        """
        if error.span is None:
            return False
        key = error.verbose_failure_id or id(error), error.span, error.span.snapshot
        if key in self.sources:
            return False
        self.sources.add(key)
        return True

    def claim_evaluation(self, frames: tuple[EvaluationContextFrame, ...], masked: bool) -> bool:
        """Reserve new context without using failure correlation as identity.

        :param frames: Detached evaluation evidence selected for this branch.
        :param masked: Effective inherited protection.
        :returns: Whether this context has not already been expanded.
        """
        if any(
            protected == masked
            and len(previous) == len(frames)
            and all(
                match_evaluation_frame(left, right)
                for left, right in zip(previous, frames, strict=True)
            )
            for previous, protected in self.evaluations
        ):
            return False
        self.evaluations.append((frames, masked))
        return True


def find_shared_evaluation_prefix(error: BaseException) -> tuple[EvaluationContextFrame, ...]:
    """Find exactly identical member contexts without comparing rendered labels.

    :param error: Candidate group, including native or evidence-free members.
    :returns: Ordered common frames, or an empty tuple when no prefix is shared.
    """
    if not isinstance(error, BaseExceptionGroup):
        return ()
    members = cast(BaseExceptionGroup[BaseException], error).exceptions
    contexts = [member.evaluation_context for member in members if isinstance(member, LclError)]
    if len(contexts) != len(members) or not contexts:
        return ()
    shared: list[EvaluationContextFrame] = []
    for frames in zip(*contexts, strict=False):
        if not all(match_evaluation_frame(frame, frames[0]) for frame in frames[1:]):
            break
        shared.append(frames[0])
    return tuple(shared)


def match_evaluation_frame(left: EvaluationContextFrame, right: EvaluationContextFrame) -> bool:
    """Compare evidence including snapshots excluded from source-span equality.

    :param left: First detached context frame.
    :param right: Other detached context frame.
    :returns: Whether positions, source bodies, expressions, values and masks match.
    """
    return (
        left == right
        and left.span.snapshot == right.span.snapshot
        and all(
            first.span.snapshot == second.span.snapshot
            for first, second in zip(left.used_values, right.used_values, strict=True)
        )
    )
