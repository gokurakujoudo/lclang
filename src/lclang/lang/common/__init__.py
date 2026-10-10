"""Shared language records, versions and declaration markers.

Exports ``LclRecord``, ``LCL_V1``, ``LanguageVersion``, ``NEED_OVERRIDE``,
``RUNTIME_OVERRIDE``, ``OverrideMarker``, ``FRAME_PROXY``, ``FrameProxyMarker``.
"""

from lclang.lang.common.frame_proxy_marker import FRAME_PROXY, FrameProxyMarker
from lclang.lang.common.language_version import LCL_V1, LanguageVersion
from lclang.lang.common.lcl_record import LclRecord
from lclang.lang.common.override_marker import NEED_OVERRIDE, RUNTIME_OVERRIDE, OverrideMarker

# Unitless names curate the supported shared types.
__all__ = [
    "LclRecord",
    "LCL_V1",
    "LanguageVersion",
    "NEED_OVERRIDE",
    "RUNTIME_OVERRIDE",
    "OverrideMarker",
    "FRAME_PROXY",
    "FrameProxyMarker",
]
