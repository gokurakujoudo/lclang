"""Optional utility subsystems for lclang applications.

Exports ``CallableBox``, ``ValueBox``, ``Environment``, ``SnowflakeGenerator``, ``env``,
``flatten_to_dict``, ``invoke``, ``safe_repr``, ``make_multi_log_lines``,
``make_repr_lines``.
"""

from lclang.utils.callback_invocation import invoke
from lclang.utils.dataclass_flattening import flatten_to_dict
from lclang.utils.process_environment import Environment, env
from lclang.utils.snowflake_id import SnowflakeGenerator
from lclang.utils.value_box import CallableBox, ValueBox
from lclang.utils.value_representation import make_multi_log_lines, make_repr_lines, safe_repr

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = [
    "CallableBox",
    "ValueBox",
    "Environment",
    "SnowflakeGenerator",
    "env",
    "flatten_to_dict",
    "invoke",
    "safe_repr",
    "make_multi_log_lines",
    "make_repr_lines",
]
