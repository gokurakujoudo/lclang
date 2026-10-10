"""Public canonical source-printer service.

Exports ``to_source``.
"""

from lclang.lang.engine.printer.source_printer import to_source

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = ["to_source"]
