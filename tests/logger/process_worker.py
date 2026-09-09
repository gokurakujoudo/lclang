"""Independent interpreter fixture for process-local threaded file output."""

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor

from lclang.logger import use_logger, use_logger_handler


async def produce(directory: str, identity: str, threads: int) -> None:
    """Write identifiable complete records from independent producer threads."""
    async with use_logger_handler(
        {"console": {"enabled": False}, "file": {identity: {"directory": directory}}}
    ) as runtime:
        logger = await use_logger(name=identity)

        def batch(number: int) -> None:
            for index in range(20):
                logger.info("record:%s:%d:%d", identity, number, index)

        with ThreadPoolExecutor(max_workers=threads) as executor:
            list(executor.map(batch, range(threads)))
    assert runtime.metrics.records_written == threads * 20


if __name__ == "__main__":
    asyncio.run(produce(sys.argv[1], sys.argv[2], int(sys.argv[3])))
