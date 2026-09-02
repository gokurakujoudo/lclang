"""Curated async-first configuration loading and evaluation API."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from lclang.config.files import FileConfigResolver
from lclang.config.limits import ConfigLoadLimits
from lclang.config.loader import ConfigLoader
from lclang.config.protocols import ConfigSourceResolver
from lclang.config.result import Config
from lclang.runtime import EvaluationLimits, Frame, Preset
from lclang.types import FrameId


async def load_config(
    path: str | Path,
    *,
    resolver: ConfigSourceResolver | None = None,
    limits: ConfigLoadLimits | None = None,
    overrides: Mapping[str, object] | None = None,
) -> Config:
    """Load and recursively expand one `.lclcfg` root.

    :param path: Root configuration path.
    :param resolver: Optional host-controlled resolver; filesystem is default.
    :param limits: Optional resource ceilings.
    :param overrides: Literal or semantic values overriding dynamic using context.
    :returns: Immutable expanded configuration snapshot.
    :raises Exception: If retrieval, parsing, expansion, or limits fail.

    .. note::
       Omitting the resolver opts into local filesystem access.
    """
    selected_resolver = FileConfigResolver() if resolver is None else resolver
    selected_limits = ConfigLoadLimits() if limits is None else limits
    return await ConfigLoader(selected_resolver, selected_limits).load(
        path,
        overrides=overrides,
    )


async def evaluate_config(
    config: Config,
    name: str,
    *,
    preset: Preset | None = None,
    values: Mapping[str, object] | None = None,
    parent: Frame | None = None,
    limits: EvaluationLimits | None = None,
) -> object:
    """Evaluate one winning definition through a guaranteed-cleanup Frame.

    :param config: Immutable expanded configuration.
    :param name: Definition name to evaluate.
    :param preset: Optional reusable host bindings.
    :param values: Optional call-local host bindings.
    :param parent: Optional borrowed parent Frame.
    :param limits: Optional evaluation limits.
    :returns: Evaluated definition value.
    :raises TypeError: If *config* is not a Config.
    :raises Exception: If Frame construction, evaluation, or cleanup fails.

    .. note::
       The temporary Frame is closed even when lookup fails.
    """
    if not isinstance(config, Config):
        raise TypeError("evaluate_config requires a Config")
    factory = config.frame_factory(preset=preset, limits=limits)
    frame = factory.create(
        FrameId(f"config:{config.root_origin.name}"),
        values=values,
        parent=parent,
    )
    try:
        return await frame.get(name)
    finally:
        await frame.close()
