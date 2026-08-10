"""Run the built-in lclang CLI through ``python -m lclang.cli``."""

import asyncio

from lclang.cli.application import LCLANG_CLI_ENTRANCE

if __name__ == "__main__":
    raise SystemExit(asyncio.run(LCLANG_CLI_ENTRANCE.run()))
