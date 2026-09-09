"""Public `.lclcfg` parsing, loading, provenance, and runtime bridge."""

from lclang.config.api import evaluate_config, load_config
from lclang.config.errors import (
    LclConfigCycleError,
    LclConfigLifecycleError,
    LclConfigLimitError,
    LclConfigSyntaxError,
    LclConfigUsingError,
    LclConfigVersionError,
)
from lclang.config.files import FileConfigResolver
from lclang.config.limits import ConfigLoadLimits
from lclang.config.loader import ConfigLoader
from lclang.config.model import ConfigDeclaration, ConfigDefinition, ConfigDocument, ConfigUsing
from lclang.config.parser import parse_config
from lclang.config.protocols import ConfigSourceResolver
from lclang.config.result import Config
from lclang.config.sources import ResolvedConfigSource
from lclang.errors import LclConfigError

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
    "FileConfigResolver",
    "LclConfigCycleError",
    "LclConfigError",
    "LclConfigLifecycleError",
    "LclConfigLimitError",
    "LclConfigSyntaxError",
    "LclConfigUsingError",
    "LclConfigVersionError",
    "ResolvedConfigSource",
    "evaluate_config",
    "load_config",
    "parse_config",
]
