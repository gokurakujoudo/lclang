"""Detached immutable records for loading and evaluation diagnostics."""

from dataclasses import dataclass
from typing import Literal, cast

from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor
from lclang.error.codes.core import Code as core_codes
from lclang.source import SourceOrigin, SourceSpan


@guard_constructor(LclValidationError, core_codes.NATIVE_831)
@dataclass(frozen=True, slots=True)
class DiagnosticValue:
    """Describe one value already read during the failed evaluation.

    :param name: Actual runtime or lexical name.
    :param span: Source occurrence that requested the value.
    :param type_name: Concrete type label at failure time.
    :param value: Protected, bounded value representation, never the host object.
    :param masked: Whether the value was redacted before representation.
    :raises LclValidationError: If a field has an unsupported type.
    :raises LclValidationError: If the name or type label is empty.
    """

    name: str
    span: SourceSpan
    type_name: str
    value: str
    masked: bool = False

    def __post_init__(self) -> None:
        """Validate a detached read snapshot.

        :raises LclValidationError: If a snapshot field has an unsupported type.
        :raises LclValidationError: If the name or type label is empty.
        """
        if not all(isinstance(item, str) for item in (self.name, self.type_name, self.value)):
            raise LclValidationError(
                "diagnostic value names, types, and representations must be strings",
                code=core_codes.E31_DIAGNOSTIC_VALUE_NAMES_TYPES_AND_REPRESENTATIONS_MUST_BE_STRINGS,
            )
        if not isinstance(self.span, SourceSpan) or not isinstance(self.masked, bool):
            raise LclValidationError(
                "diagnostic value requires a SourceSpan and Boolean mask",
                code=core_codes.E31_DIAGNOSTIC_VALUE_REQUIRES_A_SOURCESPAN_AND_BOOLEAN_MASK,
            )
        if not self.name or not self.type_name:
            raise LclValidationError(
                "diagnostic value name and type cannot be empty",
                code=core_codes.E31_DIAGNOSTIC_VALUE_NAME_AND_TYPE_CANNOT_BE_EMPTY,
            )


@guard_constructor(LclValidationError, core_codes.NATIVE_831)
@dataclass(frozen=True, slots=True)
class EvaluationContextFrame:
    """Describe an active definition, function call, or dynamic file target.

    :param name: Actual qualified owner or lexical function label.
    :param span: Source range of the evaluated expression.
    :param expression: Source-oriented expression fallback for source-less ASTs.
    :param used_values: Immutable protected read snapshots in occurrence order.
    :param kind: Unitless frame category selected by the evaluation boundary.
    :param masked: Whether the owner expression and failure must be redacted.
    :raises LclValidationError: If a frame field has an unsupported type.
    :raises LclValidationError: If the name is empty or kind is unsupported.
    """

    name: str
    span: SourceSpan
    expression: str
    used_values: tuple[DiagnosticValue, ...] = ()
    kind: Literal["definition", "function", "target"] = "definition"
    masked: bool = False

    def __post_init__(self) -> None:
        """Validate the immutable failure context.

        :raises LclValidationError: If a frame field has an unsupported type.
        :raises LclValidationError: If the name or category is invalid.
        """
        if not isinstance(self.name, str) or not isinstance(self.expression, str):
            raise LclValidationError(
                "evaluation context name and expression must be strings",
                code=core_codes.E31_DIAGNOSTIC_VALUE_NAMES_TYPES_AND_REPRESENTATIONS_MUST_BE_STRINGS,
            )
        if not isinstance(self.span, SourceSpan) or not isinstance(self.masked, bool):
            raise LclValidationError(
                "evaluation context requires a SourceSpan and Boolean mask",
                code=core_codes.E31_EVALUATION_CONTEXT_REQUIRES_A_SOURCESPAN_AND_BOOLEAN_MASK,
            )
        validate_record_tuple(self.used_values, DiagnosticValue, "used values")
        if not self.name or self.kind not in {"definition", "function", "target"}:
            raise LclValidationError(
                "evaluation context name or kind is invalid",
                code=core_codes.E31_EVALUATION_CONTEXT_NAME_OR_KIND_IS_INVALID,
            )


@guard_constructor(LclValidationError, core_codes.NATIVE_831)
@dataclass(frozen=True, slots=True)
class ConfigLoadFrame:
    """Describe one root load or source-level file introduction.

    :param origin: Importing file's unchanged physical or logical origin.
    :param declaration_span: Introduction declaration, or None for a root load.
    :param target: Requested target text, or None before dynamic target resolution.
    :raises LclValidationError: If any frame field has an unsupported type.
    """

    origin: SourceOrigin
    declaration_span: SourceSpan | None = None
    target: str | None = None

    def __post_init__(self) -> None:
        """Validate the detached loading frame.

        :raises LclValidationError: If any frame field has an unsupported type.
        """
        if not isinstance(self.origin, SourceOrigin):
            raise LclValidationError(
                "config load origin must be a SourceOrigin",
                code=core_codes.E31_CONFIG_LOAD_ORIGIN_MUST_BE_A_SOURCEORIGIN,
            )
        if self.declaration_span is not None and not isinstance(self.declaration_span, SourceSpan):
            raise LclValidationError(
                "config load declaration span must be a SourceSpan or None",
                code=core_codes.E31_CONFIG_LOAD_DECLARATION_SPAN_MUST_BE_A_SOURCESPAN_OR_NONE,
            )
        if self.target is not None and not isinstance(self.target, str):
            raise LclValidationError(
                "config load target must be a string or None",
                code=core_codes.E31_DIAGNOSTIC_VALUE_NAMES_TYPES_AND_REPRESENTATIONS_MUST_BE_STRINGS,
            )


def validate_record_tuple(value: object, record_type: type[object], label: str) -> None:
    """Validate one public immutable diagnostic sequence.

    :param value: Candidate record tuple from an untyped caller.
    :param record_type: Concrete record type accepted by the sequence.
    :param label: Human-readable sequence name for validation failures.
    :raises LclValidationError: If the value is not a tuple of the required records.
    """
    if not isinstance(value, tuple) or any(
        not isinstance(item, record_type) for item in cast(tuple[object, ...], value)
    ):
        raise LclValidationError(
            f"{label} must be a tuple of {record_type.__name__} records",
            code=core_codes.E31_VALUE_MUST_BE_A_TUPLE_OF_VALUE_RECORDS,
        )
