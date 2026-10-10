"""Enumerate builtin codes and their parent-relative classification paths."""

from enum import StrEnum

from lclang.error.base import LclValidationError
from lclang.error.codes.causes import (
    CATEGORIES,
    CATEGORY_OVERRIDES,
    CAUSE_OVERRIDES,
    CAUSES,
    REFINEMENTS,
)
from lclang.error.codes.cli import Code as CliCode
from lclang.error.codes.configuration import Code as ConfigurationCode
from lclang.error.codes.core import Code as CoreCode
from lclang.error.codes.domains import DOMAINS, SUBSYSTEMS
from lclang.error.codes.general import Code as GeneralCode
from lclang.error.codes.general import Code as general_codes
from lclang.error.codes.language import Code as LanguageCode
from lclang.error.codes.logging import Code as LoggingCode
from lclang.error.codes.operations import OPERATIONS
from lclang.error.codes.runtime import Code as RuntimeCode
from lclang.error.codes.standard import Code as StandardCode
from lclang.error.codes.utilities import Code as UtilitiesCode
from lclang.error.codes.workflow import Code as WorkflowCode

# Unitless enum types are the source of builtin identifiers; no registry initialization runs.
CODE_ENUMS: tuple[type[StrEnum], ...] = (
    GeneralCode,
    LanguageCode,
    RuntimeCode,
    ConfigurationCode,
    CliCode,
    WorkflowCode,
    LoggingCode,
    UtilitiesCode,
    CoreCode,
    StandardCode,
)


def get_error_codes() -> tuple[str, ...]:
    """Return every registered builtin code in numeric order.

    :returns: Immutable code snapshot, excluding application-defined identifiers.
    """
    return tuple(sorted(str(member) for group in CODE_ENUMS for member in group))


def get_error_code_path(code: str) -> tuple[str, ...]:
    """Explain all six positions of a registered builtin identifier.

    :param code: Builtin identifier, including its LCL prefix.
    :returns: Domain, subsystem, operation, failure category, cause, and refinement labels.
    :raises LclValidationError: If the input is not text or is unregistered.
    """
    if not isinstance(code, str):
        raise LclValidationError(
            "registry code must be text", code=general_codes.REGISTRY_CODE_TYPE
        )
    member = next((item for group in CODE_ENUMS for item in group if str(item) == code), None)
    if member is None:
        raise LclValidationError("unregistered builtin error code", code=general_codes.UNKNOWN_CODE)
    digits = code[3:]
    label = member.name
    if label.startswith("E") and label[1:3].isdigit():
        label = label[4:]
    refinement = REFINEMENTS.get(code, label.replace("_", " ").lower())
    return (
        DOMAINS[digits[0]],
        SUBSYSTEMS.get(digits[:2], "Unspecified subsystem"),
        OPERATIONS.get(digits[:3], "Unspecified operation"),
        CATEGORY_OVERRIDES.get(
            digits[:4], CATEGORIES.get(digits[3], "Unspecified failure category")
        ),
        CAUSE_OVERRIDES.get(digits[:5], CAUSES.get(digits[3:5], "Unspecified cause")),
        "No further refinement" if digits[5] == "0" else refinement,
    )
