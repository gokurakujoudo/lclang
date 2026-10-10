"""Uniform human-readable diagnostics built from detached failure records.

Defines ``render_error``, ``render_failure``, ``select_error_action``.
"""

from typing import cast

from lclang.error.exception_base import LclError


def render_error(error: LclError) -> str:
    """Render complete loading and evaluation paths with a final failure reason.

    :param error: Structured failure whose records already contain value snapshots.
    :returns: English multiline diagnostic without a terminal newline.
    """
    from lclang.common.binding_mask import MASKED_VALUE
    from lclang.error import LclError
    from lclang.error.source_excerpt import render_source_excerpt, render_source_location

    frames = tuple(frame for frame in error.evaluation_context if frame.kind != "target")
    generated = {frame.name for frame in error.evaluation_context if frame.kind == "target"}
    variable_stack = tuple(name for name in error.variable_stack if name not in generated)
    if error.config_stack:
        lines = [
            f'Error in loading config file "{error.config_stack[0].origin.name}" [{error.code}]:'
        ]
        for loading_frame in error.config_stack:
            if loading_frame.declaration_span is None:
                continue
            lines.append("  at " + render_source_location(loading_frame.declaration_span))
            lines.extend(
                "    " + line
                for line in render_source_excerpt(loading_frame.declaration_span, underline=False)
            )
    elif frames or variable_stack:
        name = frames[0].name if frames else variable_stack[0]
        lines = [f"Error in evaluating {name} [{error.code}]:"]
    else:
        action = select_error_action(error.default_code) or select_error_action(error.code)
        lines = [f"Error{action} [{error.code}]:"]
    for frame in frames:
        location = (
            ""
            if str(frame.span.origin.name) == "<unknown>"
            else " at " + render_source_location(frame.span)
        )
        lines.append(f"  {frame.name}{location}")
        if frame.masked:
            lines.append("    " + MASKED_VALUE)
        else:
            span = error.span if frame is frames[-1] and error.span is not None else frame.span
            excerpt = render_source_excerpt(span, underline=frame is frames[-1])
            lines.extend("    " + line for line in (excerpt or [frame.expression]))
        for value in frame.used_values:
            payload = MASKED_VALUE if value.masked else f"({value.type_name}) {value.value}"
            lines.append(f"    {value.name} = {payload}")
    if not frames:
        lines.extend("  " + name for name in variable_stack)
        if error.span is not None and not any(
            frame.declaration_span == error.span for frame in error.config_stack
        ):
            lines.append("  at " + render_source_location(error.span))
            excerpt = [MASKED_VALUE] if error.masked else render_source_excerpt(error.span)
            lines.extend("    " + line for line in excerpt)
    for note in getattr(error, "__notes__", ()):
        lines.append("Context: " + (MASKED_VALUE if error.masked else note))
    cause = error.__cause__
    if isinstance(cause, LclError):
        if not (cause.evaluation_context or cause.config_stack):
            lines.append("Cause: " + (MASKED_VALUE if error.masked else error.message))
        lines.extend("  " + line for line in render_error(cause).splitlines())
    else:
        reason = error.message
        if cause is not None and not isinstance(cause, LclError):
            if error.native_cause is None:
                error.freeze_native_cause(cause)
            native = error.native_cause or type(cause).__name__
            reason = native if native == reason else f"{reason}: {native}"
        if error.masked or any(frame.masked for frame in frames):
            reason = MASKED_VALUE
        lines.append("Cause: " + reason)
    if isinstance(error, ExceptionGroup):
        for index, member in enumerate(cast(ExceptionGroup[Exception], error).exceptions, 1):
            lines.append(f"  Failure {index}:")
            lines.extend(
                "    " + line
                for line in render_failure(member, action="handling failure").splitlines()
            )
    return "\n".join(lines)


def render_failure(error: BaseException, *, action: str) -> str:
    """Render a structured or native failure at an application boundary.

    :param error: Original exception, without replacing its cause or traceback.
    :param action: English operation used when no LCL action is available.
    :returns: Shared multiline diagnostic retaining external failure wording.
    """
    from lclang.error import LclError
    from lclang.utils.value_representation import safe_repr

    if isinstance(error, LclError):
        diagnostic = render_error(error)
        if not (error.evaluation_context or error.config_stack or error.variable_stack):
            lines = diagnostic.splitlines()
            lines[0] = f"Error in {action} [{error.code}]:"
            diagnostic = "\n".join(lines)
        return diagnostic
    from lclang.error.codes.e0_general_error_code import GeneralErrorCode
    from lclang.error.native_wrap import is_ordinary_failure

    reason = safe_repr(error, renderer=str, max_length=None)
    label = (
        f" [{GeneralErrorCode.E22_NATIVE_EXCEPTION_DIAGNOSTIC}]"
        if is_ordinary_failure(error)
        else ""
    )
    diagnostic = f"Error in {action}{label}:\nCause: {type(error).__name__}: {reason}"
    cause: BaseException | None = error.__cause__
    if isinstance(cause, (LclError, BaseExceptionGroup)):
        cause_diagnostic = (
            render_error(cause)
            if isinstance(cause, LclError)
            else render_failure(
                cast(BaseExceptionGroup[BaseException], cause), action="handling cause"
            )
        )
        diagnostic += "\n" + "\n".join("  " + line for line in cause_diagnostic.splitlines())
    if isinstance(error, BaseExceptionGroup):
        for index, member in enumerate(
            cast(BaseExceptionGroup[BaseException], error).exceptions, 1
        ):
            diagnostic += f"\n  Failure {index}:\n" + "\n".join(
                "    " + line
                for line in render_failure(member, action="handling failure").splitlines()
            )
    return diagnostic


def select_error_action(code: str) -> str:
    """Choose the default stage for errors lacking active operation records.

    :param code: Stable structured error code.
    :returns: Optional English action phrase, including its leading separator.
    """
    if code.startswith(("LCL11", "LCL12", "LCL31")) or code == "LCL100000":
        return " in parsing source"
    if code == "LCL230000":
        return " in resolving a variable"
    if code.startswith(("LCL13", "LCL2")):
        return " in evaluating an expression"
    if code.startswith("LCL3"):
        return " in loading configuration"
    if code.startswith("LCL4"):
        return " in command-line usage"
    if code.startswith("LCL5"):
        return " in executing a workflow"
    if code.startswith("LCL6"):
        return " in logging"
    if code.startswith("LCL7"):
        return " in a utility operation"
    if code.startswith("LCL9"):
        return " in a standard-library operation"
    return ""
