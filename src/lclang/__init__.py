"""Public package for the lclang configuration language."""

from lclang._version import __version__
from lclang.api import (
    LCL_BUILTINS,
    LCL_IMPORTS,
    LCL_ROOT,
    LCL_RUNTIME,
    define_frame,
    define_module,
)
from lclang.ast import LclAstNode, LclConstant, LclName, LclTuple, LclVisitor
from lclang.error import (
    LclAttributeError,
    LclCircularDependencyError,
    LclCliError,
    LclCliUsageError,
    LclClosedFrameError,
    LclConfigError,
    LclError,
    LclErrorGroup,
    LclEvaluationError,
    LclLoggerError,
    LclNameError,
    LclStandardError,
    LclStateError,
    LclSyntaxError,
    LclUtilityError,
    LclValidationError,
    LclWorkflowError,
)
from lclang.error.context import ConfigLoadFrame, DiagnosticValue, EvaluationContextFrame
from lclang.lang import parse_expression, to_source
from lclang.override_markers import NEED_OVERRIDE, RUNTIME_OVERRIDE, OverrideMarker
from lclang.records import LclRecord
from lclang.runtime import (
    FRAME_PROXY,
    NO_FALLBACK,
    DependencySnapshot,
    EvaluationLimits,
    Frame,
    FrameFactory,
    FrameProxy,
    Module,
    Preset,
)
from lclang.source import SourceOrigin, SourcePosition, SourceSnapshot, SourceSpan
from lclang.stdlib import STANDARD_PRESET
from lclang.types import FrameId, ModuleName, SourceName, VarName
from lclang.version import LCL_V1, LanguageVersion

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = [
    "LCL_BUILTINS",
    "LCL_IMPORTS",
    "LCL_ROOT",
    "LCL_RUNTIME",
    "LCL_V1",
    "FrameId",
    "DependencySnapshot",
    "EvaluationLimits",
    "Frame",
    "FrameFactory",
    "FrameProxy",
    "FRAME_PROXY",
    "LanguageVersion",
    "LclAstNode",
    "LclCircularDependencyError",
    "LclCliError",
    "LclCliUsageError",
    "LclClosedFrameError",
    "LclConfigError",
    "LclConstant",
    "LclError",
    "LclAttributeError",
    "LclErrorGroup",
    "LclValidationError",
    "LclStateError",
    "LclWorkflowError",
    "LclLoggerError",
    "LclUtilityError",
    "LclStandardError",
    "LclEvaluationError",
    "LclNameError",
    "LclRecord",
    "LclName",
    "LclSyntaxError",
    "LclTuple",
    "LclVisitor",
    "ModuleName",
    "Module",
    "NO_FALLBACK",
    "NEED_OVERRIDE",
    "RUNTIME_OVERRIDE",
    "OverrideMarker",
    "Preset",
    "STANDARD_PRESET",
    "SourceName",
    "SourceOrigin",
    "SourcePosition",
    "SourceSpan",
    "SourceSnapshot",
    "ConfigLoadFrame",
    "DiagnosticValue",
    "EvaluationContextFrame",
    "VarName",
    "__version__",
    "define_frame",
    "define_module",
    "parse_expression",
    "to_source",
]
