"""StandardLibraryErrorCode vocabulary.

Defines ``StandardLibraryErrorCode``.
"""

from enum import StrEnum


class StandardLibraryErrorCode(StrEnum):
    """Identify unitless six-digit standard failures.

    Values follow domain, subsystem, operation, category, cause and refinement.
    Exx names retain the subsystem and operation digits within this domain.
    """

    # Unitless identifiers follow the error reference and identify detected failure reasons.
    E00_STANDARD = "LCL900000"
    E11_MANIFEST_ENTRIES_MUST_BE_STDLIBENTRY_VALUES = "LCL911191"
    E11_DUPLICATE_STANDARD_LIBRARY_ENTRY_NAME = "LCL911231"
    E11_INVALID_STANDARD_LIBRARY = "LCL911251"
    E11_STANDARD_LIBRARY_SUMMARY_MUST_BE_ONE_NON_BLANK_LINE = "LCL911271"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E11_BUILTIN_MANIFEST_NATIVE_FAILURE = "LCL911890"
    E21_JSON_DECODE_INPUT_MUST_BE_A_STRING = "LCL921111"
    E21_JSON_VALUE_TYPE = "LCL921191"
    E21_JSON_KEY_TYPE = "LCL921192"
    E21_JSON_NONFINITE = "LCL921221"
    E21_JSON_CYCLE = "LCL921281"
    E21_JSON_SYNTAX = "LCL921491"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E21_JSON_CODEC_NATIVE_FAILURE = "LCL921890"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E31_ITERABLE_FUNCTION_NATIVE_FAILURE = "LCL931890"
    E41_YMD_MUST_BE_A_STRING = "LCL941111"
    E41_INPUT_MUST_BE_A_DATE = "LCL941171"
    E41_INVALID_DATE = "LCL941221"
    E41_YMD_MUST_CONTAIN_EXACTLY_EIGHT_ASCII_DIGITS = "LCL941271"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E41_DATE_CONVERSION_NATIVE_FAILURE = "LCL941890"
    E51_DATA_LOOKUP_INPUT_MUST_BE_A_MAPPING = "LCL951121"
    E51_DATA_MERGE_INPUTS_MUST_BE_MAPPINGS = "LCL951122"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E51_MAPPING_FUNCTION_NATIVE_FAILURE = "LCL951890"
    E61_TEXT_SEPARATOR_MUST_BE_A_STRING = "LCL961111"
    E61_KEEP_ENDS_MUST_BE_A_BOOLEAN = "LCL961141"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E61_TEXT_FUNCTION_NATIVE_FAILURE = "LCL961890"
    E71_RECURSIVE_BUILDER_MUST_BE_CALLABLE = "LCL971161"
    E71_RECURSIVE_BUILDER_MUST_RETURN_A_CALLABLE = "LCL971162"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E71_RECURSIVE_FUNCTION_NATIVE_FAILURE = "LCL971890"
    E91_STDLIB_ASSEMBLY_REQUIRES_STDLIBMANIFEST_VALUES = "LCL991191"
    E91_DUPLICATE_STANDARD_LIBRARY_NAMESPACE = "LCL991231"
    E91_NAMESPACE_ATTRIBUTE_NOT_FOUND = "LCL991391"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E91_STDLIB_NAMESPACE_NATIVE_FAILURE = "LCL991890"


# Unitless export names expose this reviewed error vocabulary.
__all__ = ["StandardLibraryErrorCode"]
