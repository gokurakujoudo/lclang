"""Hierarchical diagnostic codes for general."""

from enum import StrEnum


class Code(StrEnum):
    """Name unitless six-digit general diagnostic categories.

    Values follow the maintained error reference: domain, subsystem, operation,
    failure category, cause, and refinement. Zero terminates a classification.
    """

    # Unitless identifiers follow the reference taxonomy; named leaves distinguish detected causes.
    BASE = "LCL000000"
    VALIDATION = "LCL011000"
    STATE = "LCL012000"
    ATTRIBUTE = "LCL013000"
    GROUP = "LCL021910"
    GROUP_MEMBER = "LCL021811"
    GROUP_CONTENT = "LCL021111"
    MESSAGE_TYPE = "LCL011111"
    SPAN_TYPE = "LCL011181"
    MESSAGE_EMPTY = "LCL011211"
    STACK_TYPE = "LCL011131"
    LOAD_FRAME_TYPE = "LCL011182"
    FROZEN_ATTRIBUTE = "LCL013611"
    CONSTRUCTOR_CALL = "LCL011191"
    UNKNOWN_CODE = "LCL014211"
    REGISTRY_CODE_TYPE = "LCL014111"
    NATIVE_DIAGNOSTIC = "LCL022890"
    CALL_SIGNATURE = "LCL031191"
    CONSTRUCTOR_OPERATION = "LCL011891"


# Unitless export names expose the reviewed code vocabulary.
__all__ = ["Code"]
