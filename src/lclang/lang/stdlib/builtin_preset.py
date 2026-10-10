"""Stable reviewed manifests and assembled standard-library preset.

Declares ``STANDARD_MANIFESTS``, ``STANDARD_PRESET``.
"""

from __future__ import annotations

from lclang.lang.stdlib.builtin_manifest import StdlibEntry, StdlibManifest
from lclang.lang.stdlib.iterable_function import collect, first
from lclang.lang.stdlib.json_codec import json_decode, json_encode
from lclang.lang.stdlib.mapping_function import lookup, merge
from lclang.lang.stdlib.stdlib_namespace import assemble_stdlib
from lclang.lang.stdlib.text_function import join, lines

# Unitless manifest and preset objects below come from the curated standard-library inventory.
# Explicit assembly preserves reviewed exports and read-only bindings rather than discovering
# arbitrary Python members.
STANDARD_MANIFESTS = (
    StdlibManifest(
        "iter",
        (
            StdlibEntry("collect", collect, "Collect sync or async items."),
            StdlibEntry("first", first, "Return the first item or a default."),
        ),
    ),
    StdlibManifest(
        "text",
        (
            StdlibEntry("join", join, "Join sync or async string items."),
            StdlibEntry("lines", lines, "Split text at Unicode line boundaries."),
        ),
    ),
    StdlibManifest(
        "data",
        (
            StdlibEntry("merge", merge, "Shallow-merge mappings read-only."),
            StdlibEntry("lookup", lookup, "Look up a key with a default."),
        ),
    ),
    StdlibManifest(
        "json",
        (
            StdlibEntry("encode", json_encode, "Encode strict compact JSON."),
            StdlibEntry("decode", json_decode, "Decode strict JSON text."),
        ),
    ),
)
"""Reviewed namespace manifests in stable public declaration order."""

STANDARD_PRESET = assemble_stdlib(STANDARD_MANIFESTS)
"""Immutable assembled preset containing every reviewed standard namespace."""
