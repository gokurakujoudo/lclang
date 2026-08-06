"""Stable reviewed manifests and assembled standard-library preset."""

from __future__ import annotations

from pylcl.stdlib.data import lookup, merge
from pylcl.stdlib.iterables import collect, first
from pylcl.stdlib.json_values import json_decode, json_encode
from pylcl.stdlib.manifest import StdlibEntry, StdlibManifest
from pylcl.stdlib.namespaces import assemble_stdlib
from pylcl.stdlib.text import join, lines

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
