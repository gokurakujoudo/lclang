"""Measure producer latency and throughput separately from startup and writer drain.

Run ``python -m scripts.logger_benchmark --records 1000 --threads 1 10 100``.
The temporary files and borrowed null console are closed after each measurement.
"""

import argparse
import asyncio
import json
import os
import platform
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory

from lclang.logger import use_logger, use_logger_handler


async def measure(threads: int, records: int, mode: str) -> dict[str, object]:
    """Measure complete calls using a shared start gate, then drain outside timing."""
    with TemporaryDirectory() as directory, open(os.devnull, "w") as console:  # noqa: ASYNC230
        async with use_logger_handler(
            {
                "console": {"enabled": mode != "file", "stream": console},
                "file": {"bench": {"enabled": mode != "console", "directory": directory}},
            }
        ) as runtime:
            logger = await use_logger(name="benchmark")
            gate = threading.Barrier(threads + 1)

            def producer() -> tuple[list[int], int]:
                samples: list[int] = []
                gate.wait()
                for number in range(records):
                    start = time.perf_counter_ns()
                    logger.info("benchmark record %d", number)
                    samples.append(time.perf_counter_ns() - start)
                return samples, time.perf_counter_ns()

            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = [executor.submit(producer) for _ in range(threads)]
                start = time.perf_counter_ns()
                gate.wait()
                batches = [future.result() for future in futures]
                finish = max(end for _, end in batches)
            samples = sorted(sample for batch, _ in batches for sample in batch)
            result = {
                "mode": mode,
                "threads": threads,
                "records": len(samples),
                "call_p50_us": statistics.median(samples) / 1000,
                "call_p95_us": samples[int((len(samples) - 1) * 0.95)] / 1000,
                "call_p99_us": samples[int((len(samples) - 1) * 0.99)] / 1000,
                "producer_records_per_second": len(samples) * 1e9 / (finish - start),
            }
        assert runtime.metrics.records_written == len(samples)
        return result


def main() -> None:
    """Print reproducible environment metadata and per-mode producer measurements."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=1000, help="Records per producer thread")
    parser.add_argument("--threads", type=int, nargs="+", default=[1, 10, 100])
    args = parser.parse_args()
    if args.records < 1 or any(threads < 1 for threads in args.threads):
        parser.error("records and thread counts must be positive")
    results = [
        asyncio.run(measure(threads, args.records, mode))
        for mode in ("console", "file", "both")
        for threads in args.threads
    ]
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "results": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
