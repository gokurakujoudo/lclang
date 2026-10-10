"""Typed variables used by workflow dataclass mappings."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from functools import partial
from typing import TYPE_CHECKING, Any, cast

from lclang.error import LclWorkflowError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.workflow import Code as workflow_codes

if TYPE_CHECKING:
    from lclang.workflow.projections import TaskProjection

from lclang.defaults import NO_DEFAULT, DefaultBinding, DefaultOmission
from lclang.scopes import validate_qualified_name


@guard_constructor(LclValidationError, workflow_codes.NATIVE_526)
@dataclass(frozen=True, slots=True)
class TaskVar[ValueT]:
    """Describe one named value crossing workflow task boundaries.

    :param name: Valid qualified LCL binding name.
    :param description: Human-readable help text.
    :param is_masked: Whether lclang-owned diagnostics redact the value.
    :param value_type: Python type retained for CLI documentation.
    :param default: Optional fixed fallback retained by reference.
    :param default_factory: Optional no-argument factory resolved once per execution.
    """

    name: str
    description: str
    is_masked: bool
    value_type: object
    default: object = dataclass_field(default=NO_DEFAULT, kw_only=True)
    default_factory: Callable[[], object] | None = dataclass_field(default=None, kw_only=True)

    @property
    @guard_failure(LclWorkflowError, workflow_codes.NATIVE_526)
    def quote(self) -> ValueT:
        """Return this mapping marker with its declared value type.

        :returns: This variable cast to the mapped field type.
        """
        return cast(ValueT, self)

    @guard_failure(LclWorkflowError, workflow_codes.NATIVE_526)
    def field[FieldT](self, name: str, field_type: type[FieldT]) -> TaskProjection[FieldT]:
        """Declare a typed read-only projection of a dataclass field.

        :param name: Direct declared field name.
        :param field_type: Exact annotation expected for the selected field.
        :returns: Chainable quote marker retaining this variable as its source.
        :raises LclValidationError: If the source or selected annotation is incompatible.
        :raises LclValidationError: If the field is absent.
        """
        from lclang.workflow.projections import project_field

        return project_field(self, name, field_type)


@guard_constructor(LclValidationError, workflow_codes.NATIVE_526)
class VariableDefinition[ValueT](TaskVar[ValueT]):
    """Provide generic subscription syntax for immutable workflow variables.

    :param name: Qualified LCL binding name.
    :param description: Human-readable help text.
    :param is_masked: Whether diagnostics redact the value.
    :param value_type: Runtime annotation captured by subscription.
    :param default: Fixed fallback, distinct from omission and factory defaults.
    :param default_factory: No-argument synchronous or asynchronous factory.
    """

    __slots__ = ()

    def __init__(
        self,
        name: str,
        description: str = "",
        is_masked: bool = False,
        *,
        value_type: object = None,
        default: ValueT | DefaultOmission = NO_DEFAULT,
        default_factory: Callable[[], ValueT | Awaitable[ValueT]] | DefaultOmission = NO_DEFAULT,
    ) -> None:
        """Construct a variable with the annotation captured by subscription.

        :param name: Qualified LCL binding name.
        :param description: Human-readable help text.
        :param is_masked: Whether diagnostics redact this value.
        :param value_type: Annotation injected by the subscribed constructor.
        :param default: Fixed fallback value retained by reference.
        :param default_factory: Optional no-argument per-execution factory.
        :raises LclValidationError: If subscription is absent or metadata has invalid types.
        :raises LclValidationError: If *name* is not a qualified LCL name.
        """
        if value_type is None:
            raise LclValidationError(
                "define_variable requires a type subscription",
                code=workflow_codes.E26_DEFINE_VARIABLE_REQUIRES_A_TYPE_SUBSCRIPTION,
            )
        validate_qualified_name(name)
        if not isinstance(description, str):
            raise LclValidationError(
                "workflow variable description must be text",
                code=workflow_codes.E26_WORKFLOW_VARIABLE_DESCRIPTION_MUST_BE_TEXT,
            )
        if not isinstance(is_masked, bool):
            raise LclValidationError(
                "workflow variable masked flag must be Boolean",
                code=workflow_codes.E26_WORKFLOW_VARIABLE_MASKED_FLAG_MUST_BE_BOOLEAN,
            )
        if default_factory is not NO_DEFAULT and not callable(default_factory):
            raise LclValidationError(
                "default_factory must be callable",
                code=workflow_codes.E26_DEFAULT_FACTORY_MUST_BE_CALLABLE,
            )
        factory = default_factory if callable(default_factory) else None
        DefaultBinding(default, factory)
        super().__init__(
            name,
            " ".join(description.split()),
            is_masked,
            value_type,
            default=default,
            default_factory=factory,
        )

    @classmethod
    def __class_getitem__(cls, value_type: object) -> Callable[..., VariableDefinition[Any]]:
        """Return a constructor retaining one runtime value type.

        :param value_type: Python type annotation represented by the variable.
        :returns: Typed variable constructor.
        """
        return partial(cls, value_type=type(None) if value_type is None else value_type)


# Unitless public factory alias; a generic class preserves arbitrary annotation syntax
# for type checkers while subscription captures that annotation for runtime mappings.
define_variable = VariableDefinition
