# bench_20.py  ─────────────────────────────────────────────────────────────

# python -m llmservice.bench_20
"""
Compares throughput for 20 records:
  • THREAD-POOL  (sync path)  – mimics categorize_records(batch)
  • ASYNC GATHER (async path) – mimics categorize_records_pipeline phase-3
"""

import time, asyncio, logging, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from llmservice.bench_service import BenchLLMService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    stream=sys.stdout,
)


RECORDS = 20          # simulate 20 records
THREADS = 20          # one thread per record for fairness
SEMAPHORE = 20        # same max parallelism for async path


def run_thread_pool(svc: BenchLLMService) -> float:
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        futures = [pool.submit(svc.two_lvl_sync, f"rec{i}") for i in range(RECORDS)]
        for _ in as_completed(futures):
            pass
    return time.perf_counter() - t0


async def run_async(svc: BenchLLMService) -> float:
    sem = asyncio.Semaphore(SEMAPHORE)

    async def worker(i: int):
        async with sem:
            await svc.two_lvl_async(f"rec{i}")

    t0 = time.perf_counter()
    await asyncio.gather(*(worker(i) for i in range(RECORDS)))
    return time.perf_counter() - t0


if __name__ == "__main__":
    svc = BenchLLMService(show_logs=False)  # one shared instance

    # ---- thread-pool benchmark ----------------------------------------
    sync_dt = run_thread_pool(svc)
    print(f"\nThread-pool   (20×2 calls) Δ = {sync_dt:5.2f} s")

    # ---- async benchmark ----------------------------------------------
    async_dt = asyncio.run(run_async(svc))
    print(f"Async gather  (20×2 calls) Δ = {async_dt:5.2f} s")
