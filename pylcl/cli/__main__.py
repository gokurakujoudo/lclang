"""Run the built-in pylcl CLI through ``python -m pylcl.cli``."""

import asyncio

from pylcl.cli.application import PYLCL_CLI_ENTRANCE

if __name__ == "__main__":
    raise SystemExit(asyncio.run(PYLCL_CLI_ENTRANCE.run()))
