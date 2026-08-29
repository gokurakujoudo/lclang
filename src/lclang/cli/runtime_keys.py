"""Constant keys for values owned by one CLI invocation."""

# Reserved typed as-of date binding key.
RUNTIME_AS_OF_DATE_KEY = "__as_of_date__"
# Reserved immutable CLI parameter binding key.
RUNTIME_CLI_PARAMS_KEY = "__cli_params__"
# Reserved dry-run Boolean binding key.
RUNTIME_DRYRUN_KEY = "__dryrun__"
# Reserved verbose-mode Boolean binding key.
RUNTIME_VERBOSE_KEY = "__verbose__"
# Reserved compact as-of date binding key.
RUNTIME_YMD_KEY = "__ymd__"
# Reserved local execution timestamp binding key.
RUNTIME_EXECUTION_TIMESTAMP_KEY = "__execution_timestamp__"
# Reserved selected-command binding key.
RUNTIME_COMMAND_KEY = "__command__"
# Complete set of names unavailable to user CLI declarations.
CLI_RUNTIME_KEYS = frozenset(
    {
        RUNTIME_AS_OF_DATE_KEY,
        RUNTIME_CLI_PARAMS_KEY,
        RUNTIME_DRYRUN_KEY,
        RUNTIME_VERBOSE_KEY,
        RUNTIME_YMD_KEY,
        RUNTIME_EXECUTION_TIMESTAMP_KEY,
        RUNTIME_COMMAND_KEY,
    }
)
