"""Reserved LCL keyword spellings.

Declares ``LCL_KEYWORDS``.
"""

# Unitless spellings follow the V1 lexer vocabulary and prevent ambiguous binding names.
LCL_KEYWORDS = frozenset(
    [
        "and",
        "or",
        "not",
        "if",
        "else",
        "for",
        "in",
        "is",
        "true",
        "false",
        "none",
        "raise",
        "try",
        "except",
        "finally",
        "assert",
        "with",
        "as",
    ]
)
