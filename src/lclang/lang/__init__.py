"""Language construction, parsing and evaluation API.

Exports ``LCL_BUILTINS``, ``LCL_IMPORTS``, ``LCL_ROOT``, ``LCL_RUNTIME``, ``define_frame``,
``define_module``, ``LclAstNode``, ``LclConstant``, ``LclName``, ``LclTuple``,
``LclVisitor``, ``Token``, ``TokenKind``, ``scan_tokens``, ``parse_expression``,
``to_source``, ``NO_FALLBACK``, ``DependencySnapshot``, ``EvaluationLimits``, ``Frame``,
``FrameFactory``, ``FrameProxy``, ``Module``, ``Preset``, ``STANDARD_PRESET``,
``LclRecord``, ``LCL_V1``, ``LanguageVersion``, ``NEED_OVERRIDE``, ``RUNTIME_OVERRIDE``,
``OverrideMarker``, ``FRAME_PROXY``, ``FrameProxyMarker``, ``VarName``, ``ModuleName``,
``FrameId``, ``SourceName``, ``SourceOrigin``, ``SourcePosition``, ``SourceSnapshot``,
``SourceSpan``.
"""

from lclang.common.identifiers import FrameId, ModuleName, SourceName, VarName
from lclang.common.source_location import SourceOrigin, SourcePosition, SourceSnapshot, SourceSpan
from lclang.lang.ast import LclAstNode, LclConstant, LclName, LclTuple, LclVisitor
from lclang.lang.common.frame_proxy_marker import FRAME_PROXY, FrameProxyMarker
from lclang.lang.common.language_version import LCL_V1, LanguageVersion
from lclang.lang.common.lcl_record import LclRecord
from lclang.lang.common.override_marker import NEED_OVERRIDE, RUNTIME_OVERRIDE, OverrideMarker
from lclang.lang.engine import Token, TokenKind, parse_expression, scan_tokens, to_source
from lclang.lang.runtime import (
    NO_FALLBACK,
    DependencySnapshot,
    EvaluationLimits,
    Frame,
    FrameFactory,
    FrameProxy,
    Module,
    Preset,
)
from lclang.lang.runtime.module_frame_factory import (
    LCL_BUILTINS,
    LCL_IMPORTS,
    LCL_ROOT,
    LCL_RUNTIME,
    define_frame,
    define_module,
)
from lclang.lang.stdlib import STANDARD_PRESET

# Unitless names curate the supported language API.
__all__ = [
    "LCL_BUILTINS",
    "LCL_IMPORTS",
    "LCL_ROOT",
    "LCL_RUNTIME",
    "define_frame",
    "define_module",
    "LclAstNode",
    "LclConstant",
    "LclName",
    "LclTuple",
    "LclVisitor",
    "Token",
    "TokenKind",
    "scan_tokens",
    "parse_expression",
    "to_source",
    "NO_FALLBACK",
    "DependencySnapshot",
    "EvaluationLimits",
    "Frame",
    "FrameFactory",
    "FrameProxy",
    "Module",
    "Preset",
    "STANDARD_PRESET",
    "LclRecord",
    "LCL_V1",
    "LanguageVersion",
    "NEED_OVERRIDE",
    "RUNTIME_OVERRIDE",
    "OverrideMarker",
    "FRAME_PROXY",
    "FrameProxyMarker",
    "VarName",
    "ModuleName",
    "FrameId",
    "SourceName",
    "SourceOrigin",
    "SourcePosition",
    "SourceSnapshot",
    "SourceSpan",
]
