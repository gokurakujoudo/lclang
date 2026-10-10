"""Native task and control groups expose their leaves without mutation."""

from lclang.error import render_failure


def test_native_control_group_renders_each_member_and_cleanup_cause() -> None:
    """A control group retains native types while reporting every failure."""
    exit_signal = SystemExit(2)
    failure = OSError("business")
    errors = BaseExceptionGroup("operation", [exit_signal, failure])
    cleanup = BaseExceptionGroup("cleanup", [KeyboardInterrupt("stop"), ValueError("close")])
    errors.__cause__ = cleanup
    output = render_failure(errors, action="stopping application")
    assert "Failure 1:" in output and "Failure 2:" in output
    assert "SystemExit: 2" in output and "OSError: business" in output
    assert "KeyboardInterrupt: stop" in output and "ValueError: close" in output
    assert errors.exceptions == (exit_signal, failure) and errors.__cause__ is cleanup
    assert output.splitlines()[0] == "Error in stopping application:"


def test_native_ordinary_group_renders_nested_members() -> None:
    """Application TaskGroup output retains nested native failures."""
    errors = ExceptionGroup(
        "tasks", [ValueError("first"), ExceptionGroup("child", [OSError("second")])]
    )
    output = render_failure(errors, action="running tasks")
    assert "ValueError: first" in output and "OSError: second" in output
    assert "[LCL022890]" in output
