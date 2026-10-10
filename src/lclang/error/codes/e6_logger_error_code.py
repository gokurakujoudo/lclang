"""LoggerErrorCode vocabulary.

Defines ``LoggerErrorCode``.
"""

from enum import StrEnum


class LoggerErrorCode(StrEnum):
    """Identify unitless six-digit logging failures.

    Values follow domain, subsystem, operation, category, cause and refinement.
    Exx names retain the subsystem and operation digits within this domain.
    """

    # Unitless identifiers follow the error reference and identify detected failure reasons.
    E00_LOGGER = "LCL600000"
    E11_LOGGER_TIMEZONE_EXPECTED_TEXT = "LCL611111"
    E11_LOGGER_FORMAT_EXPECTED_TEXT = "LCL611112"
    E11_LOGGER_FORMAT = "LCL611251"
    E11_LOGGER_TIMEZONE_EXPECTED_LOCAL_OR_UTC = "LCL611291"
    E11_LOGGER_FILE_SINK_IDENTIFIER_TYPE = "LCL611292"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E11_LOGGER_CONFIGURATION_NATIVE_FAILURE = "LCL611890"
    E12_LOGGER_CONFIGURATION_REQUIRES_STRING_KEYS = "LCL612111"
    E12_LOGGER_NAMES_REQUIRE_NONEMPTY_TEXT_SEQUENCE = "LCL612131"
    E12_LOGGER_FLAG_MUST_BE_BOOLEAN = "LCL612141"
    E12_LOGGER_DURATION_MUST_BE_POSITIVE_SECONDS = "LCL612221"
    E12_UNKNOWN_LOGGER_CONFIGURATION_FIELD = "LCL612291"
    E12_INVALID_LOGGING_LEVEL = "LCL612292"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E12_LOGGER_CONFIGURATION_VALIDATION_NATIVE_FAILURE = "LCL612890"
    E13_LOGGER_MUST_REMAIN_A_FRAMEPROXY_CONFIGURATION_NAMESPACE = "LCL613191"
    E13_CANNOT_RESOLVE_LOGGER_SETTING = "LCL613291"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E13_FRAME_LOGGER_CONFIGURATION_NATIVE_FAILURE = "LCL613890"
    E21_USE_LOGGER_REQUIRES_AN_ACTIVE_USE_LOGGER_HANDLER_SCOPE = "LCL621691"
    E21_ONLY_ONE_LOGGER_HANDLER_SCOPE_IS_ALLOWED_PER_PROCESS_INITIALIZE_A = "LCL621692"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E21_LOGGER_RUNTIME_NATIVE_FAILURE = "LCL621890"
    E22_LOGGER_NAME_AND_PREFIX_MUST_BE_TEXT = "LCL622111"
    E22_EMIT_LEVEL_MUST_BE_A_NONNEGATIVE_INTEGER = "LCL622221"
    E22_LOGGER_HANDLER_SCOPE_IS_CLOSING = "LCL622691"
    E22_CLEANUP_FAILURE = "LCL622811"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E22_LOGGER_SCOPE_NATIVE_FAILURE = "LCL622890"
    E22_COMPOSITE_FAILURE = "LCL622911"
    E25_STARTUP_FAILURE = "LCL625811"
    E31_CONSOLE_STREAM_TYPE = "LCL631111"
    E31_SINK_DIRECTORY_TYPE = "LCL631191"
    E31_SINK_ENCODING_NAME_TYPE = "LCL631192"
    E31_SINK_FILENAME_MUST_BE_NONEMPTY_LEAF = "LCL631211"
    E31_ENABLED_SINK_REQUIRES_DIRECTORY = "LCL631271"
    E31_SINK_FILENAME_MUST_BE_PORTABLE_LEAF = "LCL631291"
    E31_VALUE = "LCL631292"
    E31_UNSUPPORTED_SINK_FILENAME_PLACEHOLDER = "LCL631293"
    E31_UNKNOWN_SINK_ENCODING = "LCL631294"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E31_SINK_CONFIGURATION_NATIVE_FAILURE = "LCL631890"
    E32_MAX_BYTES_MUST_BE_NONNEGATIVE_INTEGER = "LCL632221"
    E32_SIZE_ROTATION_REQUIRES_POSITIVE_MAX_BYTES = "LCL632222"
    E32_INVALID_ROTATION_INTERVAL = "LCL632223"
    E32_INVALID_ROTATION_MODE = "LCL632251"
    E32_TIME_ROTATION_REQUIRES_INTERVAL = "LCL632271"
    E32_ALIGNED_ROTATION_REQUIRES_ONE_HOUR_OR_DAY_UTC = "LCL632272"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E32_LOG_ROTATION_NATIVE_FAILURE = "LCL632890"
    E33_SINK_NOT_OPEN = "LCL633611"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E33_FILE_OUTPUT_NATIVE_FAILURE = "LCL633890"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E34_CONSOLE_OUTPUT_NATIVE_FAILURE = "LCL634890"
    E35_WRITE_FAILURE = "LCL635811"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E35_SINK_DISPATCH_NATIVE_FAILURE = "LCL635890"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E36_LOG_QUEUE_NATIVE_FAILURE = "LCL636890"
    # Unexpected ordinary native Exception at this operation; __cause__ retains its type.
    E41_LOG_FORMATTING_NATIVE_FAILURE = "LCL641890"


# Unitless export names expose this reviewed error vocabulary.
__all__ = ["LoggerErrorCode"]
