"""Shared primitives for language and application packages.

Exports ``VarName``, ``ModuleName``, ``FrameId``, ``SourceName``, ``SourceOrigin``,
``SourcePosition``, ``SourceSnapshot``, ``SourceSpan``, ``DefaultBinding``,
``DefaultOmission``, ``NO_DEFAULT``, ``ScopedProxyValue``, ``ScopedProxyFactory``.
"""

from lclang.common.default_binding import NO_DEFAULT, DefaultBinding, DefaultOmission
from lclang.common.identifiers import FrameId, ModuleName, SourceName, VarName
from lclang.common.scoped_proxy import ScopedProxyFactory, ScopedProxyValue
from lclang.common.source_location import SourceOrigin, SourcePosition, SourceSnapshot, SourceSpan

# Unitless names curate the supported shared types.
__all__ = [
    "VarName",
    "ModuleName",
    "FrameId",
    "SourceName",
    "SourceOrigin",
    "SourcePosition",
    "SourceSnapshot",
    "SourceSpan",
    "DefaultBinding",
    "DefaultOmission",
    "NO_DEFAULT",
    "ScopedProxyValue",
    "ScopedProxyFactory",
]
