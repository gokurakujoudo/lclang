"""Optional utility subsystems for lclang applications.

Exports ``CallableBox``, ``ValueBox``, ``Environment``, ``SnowflakeGenerator``, ``env``,
``PythonCallableDefinition``,
``flatten_to_dict``, ``invoke``, ``safe_repr``, ``make_multi_log_lines``,
``make_repr_lines``, ``resolve_awaitable``, ``MASK_SUFFIX``, ``MASKED_VALUE``,
``split_masked_name``, ``normalize_masked_mapping``, ``normalize_masked_names``,
``DefaultBinding``, ``DefaultOmission``, ``NO_DEFAULT``, ``ScopedProxyFactory``,
``ScopedProxyValue``, ``scoped_proxy_factory``, ``parse_ymd``, ``to_ymd``.
"""

from lclang.utils.awaitable_resolution import resolve_awaitable
from lclang.utils.binding_mask import (
    MASK_SUFFIX,
    MASKED_VALUE,
    normalize_masked_mapping,
    normalize_masked_names,
    split_masked_name,
)
from lclang.utils.callback_invocation import invoke
from lclang.utils.dataclass_flattening import flatten_to_dict
from lclang.utils.date_conversion import parse_ymd, to_ymd
from lclang.utils.default_binding import NO_DEFAULT, DefaultBinding, DefaultOmission
from lclang.utils.process_environment import Environment, env
from lclang.utils.python_callable_definition import PythonCallableDefinition
from lclang.utils.scoped_proxy import ScopedProxyFactory, ScopedProxyValue, scoped_proxy_factory
from lclang.utils.snowflake_id import SnowflakeGenerator
from lclang.utils.value_box import CallableBox, ValueBox
from lclang.utils.value_representation import make_multi_log_lines, make_repr_lines, safe_repr

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = [
    "PythonCallableDefinition",
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
    "resolve_awaitable",
    "MASK_SUFFIX",
    "MASKED_VALUE",
    "split_masked_name",
    "normalize_masked_mapping",
    "normalize_masked_names",
    "DefaultBinding",
    "DefaultOmission",
    "NO_DEFAULT",
    "ScopedProxyFactory",
    "ScopedProxyValue",
    "scoped_proxy_factory",
    "parse_ymd",
    "to_ymd",
]
