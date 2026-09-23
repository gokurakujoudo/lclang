"""Optional utility subsystems for lclang applications."""

from lclang.utils.boxes import CallableBox, ValueBox
from lclang.utils.environment import Environment, env
from lclang.utils.invocation import invoke
from lclang.utils.representation import make_multi_log_lines, make_repr_lines, safe_repr
from lclang.utils.snowflake import SnowflakeGenerator

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = [
    "CallableBox",
    "ValueBox",
    "Environment",
    "SnowflakeGenerator",
    "env",
    "invoke",
    "safe_repr",
    "make_multi_log_lines",
    "make_repr_lines",
]

