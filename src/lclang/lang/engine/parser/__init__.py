"""Public versioned parser entry points.

Exports ``parse_expression``.
"""

from lclang.lang.engine.parser.pratt_parser import parse_expression

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = ["parse_expression"]
