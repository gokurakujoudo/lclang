"""Public `.lclcfg` parsing, loading, provenance, and runtime bridge.

Exports ``Config``, ``ConfigDefinition``, ``ConfigDeclaration``, ``ConfigDocument``,
``ConfigLoadLimits``, ``ConfigLoader``, ``ConfigSourceResolver``, ``ConfigUsing``,
``ConfigImport``, ``FileConfigResolver``, ``ResolvedConfigSource``, ``evaluate_config``,
``load_config``, ``parse_config``.
"""

from lclang.config.config_document import (
    ConfigDeclaration,
    ConfigDefinition,
    ConfigDocument,
    ConfigImport,
    ConfigUsing,
)
from lclang.config.config_loader import ConfigLoader
from lclang.config.config_loading import evaluate_config, load_config
from lclang.config.config_source import ResolvedConfigSource
from lclang.config.document_parser import parse_config
from lclang.config.file_resolver import FileConfigResolver
from lclang.config.loaded_config import Config
from lclang.config.loading_limit import ConfigLoadLimits
from lclang.config.source_resolver import ConfigSourceResolver

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = [
    "Config",
    "ConfigDefinition",
    "ConfigDeclaration",
    "ConfigDocument",
    "ConfigLoadLimits",
    "ConfigLoader",
    "ConfigSourceResolver",
    "ConfigUsing",
    "ConfigImport",
    "FileConfigResolver",
    "ResolvedConfigSource",
    "evaluate_config",
    "load_config",
    "parse_config",
]
