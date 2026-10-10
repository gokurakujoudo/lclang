"""Language grammar-version constants retain their serialized contract."""

from lclang.lang.common.language_version import LCL_V1, LanguageVersion


def test_language_v1_is_the_stable_default_constant() -> None:
    """The first public grammar version must have stable serialized value 1."""
    assert LCL_V1 is LanguageVersion.V1
    assert LCL_V1.value == "1"
