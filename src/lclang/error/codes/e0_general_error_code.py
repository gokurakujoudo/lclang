"""GeneralErrorCode vocabulary.

Defines ``GeneralErrorCode``.
"""

from enum import StrEnum


class GeneralErrorCode(StrEnum):
    """Identify unitless six-digit general failures.

    Values follow domain, subsystem, operation, category, cause and refinement.
    Exx names retain the subsystem and operation digits within this domain.
    """

    # Unitless identifiers follow the error reference and identify detected failure reasons.
    E00_UNCLASSIFIED_FAILURE = "LCL000000"
    E11_VALIDATION = "LCL011000"
    E11_MESSAGE_TYPE = "LCL011111"
    E11_STACK_TYPE = "LCL011131"
    E11_SPAN_TYPE = "LCL011181"
    E11_LOAD_FRAME_TYPE = "LCL011182"
    E11_CONSTRUCTOR_CALL = "LCL011191"
    E11_MESSAGE_EMPTY = "LCL011211"
    E11_CONSTRUCTOR_OPERATION = "LCL011891"
    E12_STATE = "LCL012000"
    E13_ATTRIBUTE = "LCL013000"
    E13_FROZEN_ATTRIBUTE = "LCL013611"
    E14_REGISTRY_CODE_TYPE = "LCL014111"
    E14_UNKNOWN_CODE = "LCL014211"
    E21_GROUP_CONTENT = "LCL021111"
    E21_GROUP_MEMBER = "LCL021811"
    E21_GROUP = "LCL021910"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E22_NATIVE_DIAGNOSTIC_RENDERING_FAILURE = "LCL022890"
    E31_CALL_SIGNATURE = "LCL031191"


# Unitless export names expose this reviewed error vocabulary.
__all__ = ["GeneralErrorCode"]
