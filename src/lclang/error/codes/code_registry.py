"""Enumerate builtin codes and their parent-relative classification paths.

Defines ``get_error_codes``, ``get_error_code_path``.
"""

from enum import StrEnum

from lclang.error.codes.domain_classification import DOMAINS, SUBSYSTEMS
from lclang.error.codes.e0_general_error_code import GeneralErrorCode
from lclang.error.codes.e1_language_error_code import LanguageErrorCode
from lclang.error.codes.e2_runtime_error_code import RuntimeErrorCode
from lclang.error.codes.e3_configuration_error_code import ConfigurationErrorCode
from lclang.error.codes.e4_cli_error_code import CliErrorCode
from lclang.error.codes.e5_workflow_error_code import WorkflowErrorCode
from lclang.error.codes.e6_logger_error_code import LoggerErrorCode
from lclang.error.codes.e7_utility_error_code import UtilityErrorCode
from lclang.error.codes.e8_data_model_error_code import DataModelErrorCode
from lclang.error.codes.e9_standard_library_error_code import StandardLibraryErrorCode
from lclang.error.codes.failure_classification import (
    CATEGORIES,
    CATEGORY_OVERRIDES,
    CAUSE_OVERRIDES,
    CAUSES,
    REFINEMENTS,
)
from lclang.error.codes.operation_classification import OPERATIONS
from lclang.error.exception_base import LclValidationError

# Unitless enum types are the source of builtin identifiers; no registry initialization runs.
CODE_ENUMS: tuple[type[StrEnum], ...] = (
    GeneralErrorCode,
    LanguageErrorCode,
    RuntimeErrorCode,
    ConfigurationErrorCode,
    CliErrorCode,
    WorkflowErrorCode,
    LoggerErrorCode,
    UtilityErrorCode,
    DataModelErrorCode,
    StandardLibraryErrorCode,
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
            "registry code must be text", code=GeneralErrorCode.E14_REGISTRY_CODE_TYPE
        )
    member = next((item for group in CODE_ENUMS for item in group if str(item) == code), None)
    if member is None:
        raise LclValidationError(
            "unregistered builtin error code", code=GeneralErrorCode.E14_UNKNOWN_CODE
        )
    digits = code[3:]
    label = member.name[4:]
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
