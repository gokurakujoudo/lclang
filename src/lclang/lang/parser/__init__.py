"""Public versioned parser entry points."""

from lclang.lang.parser.pratt import parse_expression

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = ["parse_expression"]
