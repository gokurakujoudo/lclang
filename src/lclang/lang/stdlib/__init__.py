"""Public manifest-driven standard-library assembly API.

Exports ``STANDARD_MANIFESTS``, ``STANDARD_PRESET``, ``StdlibEntry``, ``StdlibManifest``,
``StdlibNamespace``, ``RecursiveFunction``, ``assemble_stdlib``, ``collect``, ``first``,
``join``, ``json_decode``, ``json_encode``, ``lines``, ``lookup``, ``merge``, ``recursive``.
"""

from lclang.lang.stdlib.builtin_manifest import StdlibEntry, StdlibManifest
from lclang.lang.stdlib.builtin_preset import STANDARD_MANIFESTS, STANDARD_PRESET
from lclang.lang.stdlib.iterable_function import collect, first
from lclang.lang.stdlib.json_codec import json_decode, json_encode
from lclang.lang.stdlib.mapping_function import lookup, merge
from lclang.lang.stdlib.recursive_function import RecursiveFunction, recursive
from lclang.lang.stdlib.stdlib_namespace import StdlibNamespace, assemble_stdlib
from lclang.lang.stdlib.text_function import join, lines

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = [
    "STANDARD_MANIFESTS",
    "STANDARD_PRESET",
    "StdlibEntry",
    "StdlibManifest",
    "StdlibNamespace",
    "RecursiveFunction",
    "assemble_stdlib",
    "collect",
    "first",
    "join",
    "json_decode",
    "json_encode",
    "lines",
    "lookup",
    "merge",
    "recursive",
]
