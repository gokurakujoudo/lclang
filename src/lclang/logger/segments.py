"""Exclusive permanent file allocation and process-wide sequence numbers."""

from __future__ import annotations

# Existing uppercase names denote mutable process state, not constants.
# pyright: reportConstantRedefinition=false
import json
import multiprocessing
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import BinaryIO

from lclang.logger.sink_config import FileConfig, leaf_filename

# Unitless process-local sequence state survives sequential scopes; PID resets detect fork copies.
SEQUENCE_LOCK = Lock()
SEQUENCE_PID = os.getpid()
SEQUENCE = 0


def next_sequence() -> int:
    """Reserve a monotonically increasing segment number in this process.

    :returns: Positive unitless sequence number.
    """
    global SEQUENCE, SEQUENCE_PID
    with SEQUENCE_LOCK:
        pid = os.getpid()
        if pid != SEQUENCE_PID:
            SEQUENCE_PID, SEQUENCE = pid, 0
        SEQUENCE += 1
        return SEQUENCE


def path_line(label: str, path: Path, encoding: str) -> bytes:
    """Encode one physical metadata line with an escaped absolute path.

    :param label: File or continuation marker.
    :param path: Absolute segment filename.
    :param encoding: Sink text encoding.
    :returns: Encoded newline-terminated metadata.
    """
    return f"{label}: {json.dumps(str(path), ensure_ascii=False)}\n".encode(
        encoding, "backslashreplace"
    )


def create_segment(config: FileConfig) -> tuple[Path, BinaryIO, int]:
    """Create a fresh segment, retrying only exclusive-name collisions.

    :param config: Enabled file policy.
    :returns: Absolute path, owned buffered stream, and header byte count.
    :raises OSError: If directory creation or file initialization fails.
    """
    directory = Path(str(config.directory)).absolute()
    directory.mkdir(parents=True, exist_ok=True)
    base = Path(
        leaf_filename(
            config.filename.format(
                pid=os.getpid(),
                process=multiprocessing.current_process().name,
            ),
            "resolved filename",
        )
    )
    while True:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        path = directory / f"{base.stem}.{timestamp}.{next_sequence():06d}{base.suffix}"
        try:
            stream = path.open("xb")
        except FileExistsError:
            continue
        try:
            header = path_line("log file", path, config.encoding)
            stream.write(header)
            stream.flush()
        except BaseException:
            stream.close()
            raise
        return path, stream, len(header)
