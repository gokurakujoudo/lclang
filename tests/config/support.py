"""Reusable source values for configuration subsystem tests."""

from pathlib import Path

from lclang.config import ResolvedConfigSource
from lclang.source import SourceOrigin, SourcePosition, SourceSpan
from lclang.types import SourceName


def source_span(name: str = "test") -> SourceSpan:
    """Build one small internally consistent source span."""
    origin = SourceOrigin(SourceName(name))
    return SourceSpan(
        origin,
        SourcePosition(1, 1, 0),
        SourcePosition(1, 2, 1),
    )


class MappingResolver:
    """Resolve canonical paths from a mutable test-controlled text mapping."""

    def __init__(self, texts: dict[Path, str]) -> None:
        """Retain canonical text snapshots and initialize call counts."""
        self.texts = {path.resolve(strict=False): text for path, text in texts.items()}
        self.calls: dict[Path, int] = {}

    async def resolve(
        self,
        path: Path,
        *,
        importer: ResolvedConfigSource | None,
    ) -> ResolvedConfigSource:
        """Return mapped text or propagate the mapping's missing-key error."""
        del importer
        normalized = path
        self.calls[normalized] = self.calls.get(normalized, 0) + 1
        return ResolvedConfigSource(
            str(normalized),
            str(normalized),
            normalized,
            self.texts[normalized],
        )
