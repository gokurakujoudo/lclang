"""Behavioural tests for immutable CLI values."""

from datetime import date
from typing import Any, cast

import pytest

from lclang.cli import CliConfig, CliParams, CliResult, CliResultStatus, ParameterDoc
from lclang.logger import LoggerHandlerConfig

InvalidParameterDoc = cast(Any, ParameterDoc)
InvalidCliParams = cast(Any, CliParams)
InvalidCliResult = cast(Any, CliResult)
InvalidCliConfig = cast(Any, CliConfig)


def test_cli_values_are_detached_and_statuses_are_exit_codes() -> None:
    """Caller mutation cannot change params and result statuses remain integers."""
    overrides: dict[str, str | bool] = {"count": "2", "enabled": True}
    params = CliParams("python", ["admin", "run"], date(2026, 8, 9), True, None, overrides)
    overrides["count"] = "3"
    assert params.command == ("admin", "run")
    assert params.script_path == "script.py"
    assert params.verbose is False
    assert params.overrides == {"count": "2", "enabled": True}
    with pytest.raises(TypeError):
        params.overrides["count"] = "4"  # type: ignore[index]
    assert int(CliResultStatus.SUCCESS) == 0
    assert CliResult(CliResultStatus.FAILURE, "failed").description == "failed"


def test_result_shortcuts_preserve_status_text_and_constructor_validation() -> None:
    """Success and failure constructors retain Unicode, empty text, and typing."""

    class DerivedCliResult(CliResult):
        """Identify the classmethod-selected result type."""

    success = CliResult.success("完成")
    failure = CliResult.fail("")
    assert success == CliResult(CliResultStatus.SUCCESS, "完成")
    assert failure == CliResult(CliResultStatus.FAILURE, "")
    assert isinstance(DerivedCliResult.success("ok"), DerivedCliResult)
    with pytest.raises(TypeError, match="description"):
        CliResult.success(1)  # type: ignore[arg-type]


def test_parameter_and_log_contracts_reject_invalid_values() -> None:
    """Names and logging formats are validated before an invocation."""
    assert ParameterDoc("count", list[int], True, "item count").default is None
    assert ParameterDoc("meter.start", float, True, "Opening meter reading").name == "meter.start"
    assert LoggerHandlerConfig(format="%(message)s").format == "%(message)s"
    with pytest.raises(ValueError, match="identifier"):
        ParameterDoc("bad-key", str, False, "bad")


def test_parameter_defaults_and_direct_params_accept_mask_markers() -> None:
    """CLI value models normalize syntax and expose immutable mask metadata."""
    parameter = ParameterDoc("token!", str, True, "secret", "value")
    params = CliParams(
        "python",
        ["run"],
        date.today(),
        False,
        None,
        {"token!": "value"},
    )
    assert (parameter.name, parameter.masked) == ("token", True)
    assert params.overrides == {"token": "value"}
    assert params.masked_names == frozenset({"token"})


@pytest.mark.parametrize(
    "factory, error",
    [
        (lambda: InvalidParameterDoc("x", str, 1, "x"), TypeError),
        (lambda: InvalidParameterDoc("x", str, True, "x", None, 1), TypeError),
        (lambda: InvalidCliParams(1, ["run"], date.today(), False, None, {}), TypeError),
        (lambda: InvalidCliParams("", ["run"], date.today(), False, None, {}), ValueError),
        (lambda: InvalidCliParams("python", [], date.today(), False, None, {}), ValueError),
        (
            lambda: InvalidCliParams(
                "python", ["run"], date.today(), False, None, {}, script_path=1
            ),
            TypeError,
        ),
        (
            lambda: InvalidCliParams(
                "python", ["run"], date.today(), False, None, {}, script_path=""
            ),
            ValueError,
        ),
        (
            lambda: InvalidCliParams(
                "python",
                ["run"],
                date.today(),
                False,
                None,
                {},
                raw_argv=("python", ""),
            ),
            ValueError,
        ),
        (lambda: InvalidCliParams("python", ["run"], "today", False, None, {}), TypeError),
        (lambda: InvalidCliParams("python", ["run"], date.today(), 1, None, {}), TypeError),
        (lambda: InvalidCliParams("python", ["run"], date.today(), False, 1, {}), TypeError),
        (lambda: InvalidCliParams("python", ["run"], date.today(), False, "", {}), ValueError),
        (
            lambda: InvalidCliParams("python", ["run"], date.today(), False, None, {"x": 1}),
            TypeError,
        ),
        (
            lambda: InvalidCliParams("python", ["run"], date.today(), False, None, {"x": False}),
            TypeError,
        ),
        (
            lambda: InvalidCliParams("python", ["run"], date.today(), False, None, {}, 1),
            TypeError,
        ),
        (lambda: InvalidCliResult(0, "x"), TypeError),
        (lambda: InvalidCliResult(CliResultStatus.SUCCESS, 1), TypeError),
        (lambda: InvalidCliConfig(log_config=object()), TypeError),
    ],
)
def test_value_models_reject_each_invalid_public_shape(
    factory: object,
    error: type[Exception],
) -> None:
    """Every public scalar/container invariant has a direct rainy case."""
    with pytest.raises(error):
        factory()  # type: ignore[operator]


def test_integer_log_level_and_valid_config_are_supported() -> None:
    """Numeric standard-library levels remain valid effective configuration."""
    config = CliConfig(LoggerHandlerConfig(level=20))
    assert config.log_config.level == 20
