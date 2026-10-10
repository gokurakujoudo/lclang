"""Resolved configuration source values and portable path normalization.

Defines ``ResolvedConfigSource``, ``LoadedConfigSource``, ``canonical_config_path``,
``resolve_using_path``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lclang.config.config_document import ConfigDocument
from lclang.error import ConfigurationErrorCode, LclConfigError
from lclang.error.configuration_exception import LclConfigUsingError
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure


@guard_constructor(
    LclValidationError, ConfigurationErrorCode.E22_CONFIG_SOURCE_RESOLUTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class ResolvedConfigSource:
    """Describe one immutable path-backed source returned by a resolver.

    :param identity: Non-empty stable cache and cycle identity.
    :param display_name: Non-empty diagnostic source name.
    :param path: Canonical absolute `.lclcfg` path.
    :param text: Decoded Unicode source text.
    :raises LclValidationError: If identity, display name, path, or text is invalid.

    .. note::
       Identity controls caching while path controls language-visible magic.
    """

    identity: str
    display_name: str
    path: Path
    text: str

    @guard_failure(
        LclValidationError, ConfigurationErrorCode.E22_CONFIG_SOURCE_RESOLUTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Validate and canonicalize the resolver result.

        :returns: ``None``.
        :raises LclValidationError: If identity, display name, path, or text is invalid.

        .. note::
           Resolver text is retained as an immutable string snapshot.
        """
        if not self.identity:
            raise LclValidationError(
                "resolved config identity cannot be empty",
                code=ConfigurationErrorCode.E22_RESOLVED_CONFIG_IDENTITY_CANNOT_BE_EMPTY,
            )
        if not self.display_name:
            raise LclValidationError(
                "resolved config display name cannot be empty",
                code=ConfigurationErrorCode.E22_RESOLVED_CONFIG_IDENTITY_CANNOT_BE_EMPTY,
            )
        if not isinstance(self.path, Path):
            raise LclValidationError(
                "resolved config path must be a Path",
                code=ConfigurationErrorCode.E22_RESOLVED_CONFIG_PATH_MUST_BE_A_PATH,
            )
        path = self.path.resolve(strict=False)
        if path.suffix != ".lclcfg":
            raise LclValidationError(
                "resolved config path must end in .lclcfg",
                code=ConfigurationErrorCode.E22_RESOLVED_CONFIG_PATH_MUST_END_IN_LCLCFG,
            )
        if not isinstance(self.text, str):
            raise LclValidationError(
                "resolved config text must be Unicode",
                code=ConfigurationErrorCode.E22_RESOLVED_CONFIG_TEXT_MUST_BE_UNICODE,
            )
        object.__setattr__(self, "path", path)


@guard_constructor(
    LclValidationError, ConfigurationErrorCode.E22_CONFIG_SOURCE_RESOLUTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LoadedConfigSource:
    """Pair one resolved source snapshot with its parsed document.

    :param source: Immutable resolver result.
    :param document: Parsed syntax snapshot for the same path.

    .. note::
       Expansion placement is intentionally not stored in this cached value.
    """

    source: ResolvedConfigSource
    document: ConfigDocument


@guard_failure(LclConfigError, ConfigurationErrorCode.E22_CONFIG_SOURCE_RESOLUTION_NATIVE_FAILURE)
def canonical_config_path(path: str | Path) -> Path:
    """Normalize and validate one root configuration path.

    :param path: Public root path argument.
    :returns: Canonical absolute `.lclcfg` path.
    :raises LclValidationError: If *path* is not text or a Path.
    :raises LclConfigUsingError: If the exact suffix is invalid.

    .. note::
       Normalization does not read or require the target to exist.
    """
    if not isinstance(path, (str, Path)):
        raise LclValidationError(
            "config path must be text or Path",
            code=ConfigurationErrorCode.E22_CONFIG_PATH_MUST_BE_TEXT_OR_PATH,
        )
    normalized = Path(path).resolve(strict=False)
    if normalized.suffix != ".lclcfg":
        raise LclConfigUsingError(
            "config path must end in .lclcfg",
            code=ConfigurationErrorCode.E22_CONFIG_PATH_MUST_END_IN_LCLCFG,
        )
    return normalized


@guard_failure(LclConfigError, ConfigurationErrorCode.E22_CONFIG_SOURCE_RESOLUTION_NATIVE_FAILURE)
def resolve_using_path(target: str, importer: ResolvedConfigSource) -> Path:
    """Resolve one decoded target relative to its importing file.

    :param target: Non-empty decoded using target.
    :param importer: Physical source containing the declaration.
    :returns: Canonical absolute `.lclcfg` target path.
    :raises LclConfigUsingError: If the suffix is invalid.

    .. note::
       Only an exact leading `__dir__` token is expanded; later text is literal.
    """
    if target == "__dir__":
        candidate = importer.path.parent
    elif target.startswith("__dir__/"):
        candidate = importer.path.parent / target[len("__dir__/") :]
    else:
        raw = Path(target)
        candidate = raw if raw.is_absolute() else importer.path.parent / raw
    normalized = candidate.resolve(strict=False)
    if normalized.suffix != ".lclcfg":
        raise LclConfigUsingError(
            "using target must end in .lclcfg",
            code=ConfigurationErrorCode.E22_USING_TARGET_MUST_END_IN_LCLCFG,
        )
    return normalized
