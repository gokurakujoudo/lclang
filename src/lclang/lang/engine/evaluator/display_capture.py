"""Task-scoped, detached runtime display capture for verbose and CLI consumers.

Defines ``DisplayRequest``, ``RuntimeDisplayCapture``, ``capture_runtime_display``,
``render_display_value``, ``render_canonical_value``.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from lclang.error import LclValidationError
from lclang.error.verbose_context import is_verbose_enabled
from lclang.error.verbose_diagnostic import internal_render_value
from lclang.lang.ast import LclAstNode
from lclang.lang.engine.printer import to_source
from lclang.utils.text_tree import TextTree, render_text_tree, sort_display_name


@dataclass(slots=True)
class DisplayRequest:
    """Own protected text for one actual request or function call.

    :param name: Actual binding or lexical call label.
    :param label: Protected definition or value line.
    :param execution: Execution source observed before awaiting the operation.
    :param kind: Binding or call, used to distinguish function creation from invocation.
    :param masked: Sticky diagnostic mask for this request.
    :param children: Temporary descendants belonging to this root request.
    :param result: Protected completed result, never the host object.
    :param evaluation_id: Optional process-local evaluation correlation.
    """

    name: str
    label: str
    execution: str
    kind: str = "binding"
    masked: bool = False
    children: list[DisplayRequest] = field(default_factory=lambda: list[DisplayRequest]())
    result: str | None = None
    evaluation_id: str | None = None

    def freeze(self) -> TextTree:
        """Detach an alphabetical display tree from its temporary builder.

        :returns: Recursive immutable text pairs with no runtime objects.
        """
        children: list[DisplayRequest] = []
        names: set[str] = set()
        for child in self.children:
            if child.kind != "call":
                if child.name in names:
                    continue
                names.add(child.name)
            children.append(child)
        return self.label, (
            ()
            if self.masked
            else tuple(
                child.freeze()
                for child in sorted(children, key=lambda child: sort_display_name(child.name))
            )
        )


@dataclass(slots=True)
class RuntimeDisplayCapture:
    """Retain the last completed root snapshot for an explicit display consumer.

    :param tree: Detached successful or ordinary-failure tree, initially absent.
    :param result: Protected successful root result, initially absent.
    """

    tree: TextTree | None = None
    result: str | None = None

    def to_lines(self) -> list[str]:
        """Render captured text without querying the Frame after evaluation.

        :returns: Tree lines and optional completed root result.
        """
        lines = [] if self.tree is None else render_text_tree(self.tree)
        if self.result is not None:
            lines.append("Result: " + self.result)
        return lines


# Unitless context state is task-local; child evaluation Tasks inherit their
# current request node. Separate root contexts never share builders or snapshots.
ACTIVE_DISPLAY_REQUEST: ContextVar[DisplayRequest | None] = ContextVar(
    "lclang_display_request", default=None
)
ACTIVE_DISPLAY_CAPTURE: ContextVar[RuntimeDisplayCapture | None] = ContextVar(
    "lclang_display_capture", default=None
)


@contextmanager
def capture_runtime_display() -> Generator[RuntimeDisplayCapture]:
    """Collect actual runtime evidence without configuring or enabling logging.

    :returns: Capture restored on exit, including cancellation and native controls.
    """
    capture = RuntimeDisplayCapture()
    token = ACTIVE_DISPLAY_CAPTURE.set(capture)
    try:
        yield capture
    finally:
        ACTIVE_DISPLAY_CAPTURE.reset(token)


def render_display_value(value: object, *, masked: bool = False) -> str:
    """Protect one already-resolved value using canonical AST/function rendering.

    :param value: Actual completed value, never an extra lookup.
    :param masked: Sticky owner or binding mask applied before representation.
    :returns: Bounded typed payload, or empty text when the current consumers are disabled.
    """
    if not is_verbose_enabled() and ACTIVE_DISPLAY_CAPTURE.get() is None:
        return ""
    return internal_render_value(
        value,
        lambda: render_canonical_value(value),
        masked=masked,
    )


def render_canonical_value(value: object) -> str:
    """Reuse canonical AST and function text while tolerating custom AST nodes.

    :param value: Already-supplied host or computed value.
    :returns: Canonical supported AST source or the value's ordinary representation.
    """
    if isinstance(value, LclAstNode):
        try:
            return to_source(value)
        except TypeError, LclValidationError:
            pass
    return repr(value)
