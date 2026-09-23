"""Display-only derived parameter metadata, separate from runtime defaults."""

from collections.abc import Sequence
from dataclasses import dataclass

from lclang.cli.models import ParameterDoc
from lclang.defaults import DefaultBinding
from lclang.runtime import Frame


@dataclass(frozen=True, slots=True)
class DerivedParameterDoc(ParameterDoc):
    """Describe a record field without injecting a binding or checking it alone.

    :param name: Full field path.
    :param value_type: Display annotation.
    :param required: Whether construction requires this field without enclosing defaults.
    :param description: Field help text.
    :param default: Inherited binding default; derived fields leave this as None.
    :param masked: Whether field presentation is redacted.
    :param root_name: External record variable owning this field.
    :param help_default: Constructor default metadata used only for presentation.
    """

    root_name: str = ""
    help_default: DefaultBinding | None = None


def get_parameter_masks(parameters: Sequence[ParameterDoc], frame: Frame) -> frozenset[str]:
    """Propagate known record masks before CLI audits inspect derived fields.

    :param parameters: Explicit and derived command descriptions.
    :param frame: Effective invocation bindings before presentation masks are attached.
    :returns: Exact names to mask, including descendants of masked record paths.
    """
    return frozenset(
        item.name for item in parameters
        if item.masked or isinstance(item, DerivedParameterDoc) and any(
            frame.is_masked(".".join(item.name.split(".")[:index]))
            for index in range(1, len(item.name.split(".")))
        )
    )
