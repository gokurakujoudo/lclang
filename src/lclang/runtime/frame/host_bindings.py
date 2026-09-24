# Shared implementation modules intentionally access owner state.
# pyright: reportPrivateUsage=false

"""Controlled updates for Frame host-value bindings."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lclang.runtime.frame.frame import Frame

from typing import cast

from lclang.masking import normalize_masked_mapping
from lclang.runtime.frame.binding_lookup import validate_mixin_tree
from lclang.scopes import validate_binding_names


def update_host_bindings(frame: Frame, values: dict[str, object]) -> None:
    """Copy host bindings into an open Frame.

    :param frame: Concrete Frame providing the operation state.
    :param values: String-keyed host bindings applied right-biased.
    :returns: ``None`` after the atomic mapping update.
    :raises TypeError: If *values* is not a string-keyed dictionary.
    :raises ValueError: If a host-binding name is empty.
    :raises LclClosedFrameError: If Frame closing has begun.

    .. note::
       Validation and detachment finish before any owned state is changed.
    """
    if not isinstance(values, dict):
        raise TypeError("Frame mixin values must be a dictionary")
    if any(not isinstance(name, str) for name in values):
        raise TypeError("Frame mixin names must be strings")
    updates, masked_names = normalize_masked_mapping(values)
    if any(not name for name in updates):
        raise ValueError("host binding name cannot be empty")
    validate_binding_names(updates)
    frame._lifecycle.ensure_open(None)
    prospective = dict(cast(dict[str, object], frame.values))
    prospective.update(updates)
    validate_mixin_tree(frame, prospective)
    frame._values.update(updates)
    frame.masked_names = frozenset(frame.masked_names | masked_names)
