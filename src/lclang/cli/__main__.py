"""Run the built-in lclang CLI through ``python -m lclang.cli``.

This package groups the implementation modules listed in its directory.
"""

import asyncio

from lclang.cli.builtin_command import LCLANG_CLI_ENTRANCE

if __name__ == "__main__":
    raise SystemExit(asyncio.run(LCLANG_CLI_ENTRANCE.run()))
