"""Shared extraction for one-to-one tutorial document unit tests."""

from pathlib import Path

# Repository root containing the tutorial documents.
ROOT = Path(__file__).resolve().parents[2]
# Marker immediately preceding every executable chapter example.
EXECUTION_MARKER = "<!-- lclang-tutorial-exec -->"


def execute_tutorial(filename: str, expected_examples: int) -> None:
    """Compile and execute every marked Python example in one tutorial.

    :param filename: Tutorial Markdown filename beneath ``docs/tutorials``.
    :param expected_examples: Exact number of executable examples required.
    :returns: ``None`` after every independent example succeeds.
    """
    path = ROOT / "docs" / "tutorials" / filename
    text = path.read_text(encoding="utf-8")
    examples = [
        part.split("```python", 1)[1].split("```", 1)[0].strip()
        for part in text.split(EXECUTION_MARKER)[1:]
    ]
    assert len(examples) == expected_examples
    stem = path.stem.replace("-", "_")
    for index, source in enumerate(examples, start=1):
        namespace = {"__name__": f"lclang_tutorial_{stem}_{index}"}
        exec(compile(source, f"<{filename}:{index}>", "exec"), namespace)

