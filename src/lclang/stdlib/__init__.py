"""Public manifest-driven standard-library assembly API."""

from lclang.stdlib.builtins import STANDARD_MANIFESTS, STANDARD_PRESET
from lclang.stdlib.data import lookup, merge
from lclang.stdlib.iterables import collect, first
from lclang.stdlib.json_values import json_decode, json_encode
from lclang.stdlib.manifest import StdlibEntry, StdlibManifest
from lclang.stdlib.namespaces import StdlibNamespace, assemble_stdlib
from lclang.stdlib.recursion import RecursiveFunction, recursive
from lclang.stdlib.text import join, lines

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
