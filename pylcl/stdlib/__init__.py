"""Public manifest-driven standard-library assembly API."""

from pylcl.stdlib.builtins import STANDARD_MANIFESTS, STANDARD_PRESET
from pylcl.stdlib.data import lookup, merge
from pylcl.stdlib.iterables import collect, first
from pylcl.stdlib.json_values import json_decode, json_encode
from pylcl.stdlib.manifest import StdlibEntry, StdlibManifest
from pylcl.stdlib.namespaces import StdlibNamespace, assemble_stdlib
from pylcl.stdlib.recursion import RecursiveFunction, recursive
from pylcl.stdlib.text import join, lines

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
