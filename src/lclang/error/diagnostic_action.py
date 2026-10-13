"""Operation labels for diagnostic codes without active language evidence.

Defines ``select_error_action``.
"""


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
