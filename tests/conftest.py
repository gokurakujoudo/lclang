"""Deterministic project-wide property-test configuration."""

from hypothesis import settings

settings.register_profile(
    "lclang",
    max_examples=300,
    derandomize=True,
    database=None,
    deadline=None,
)
settings.load_profile("lclang")
