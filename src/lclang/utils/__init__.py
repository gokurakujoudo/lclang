"""Optional utility subsystems for lclang applications."""

from lclang.utils.environment import Environment, env
from lclang.utils.representation import safe_repr

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = [
    "Environment",
    "env",
    "safe_repr",
]

