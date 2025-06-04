# llmservice/bench_concurrency.py

# python -m llmservice.bench_concurrency
import asyncio, statistics, time, sys
from typing import List

from llmservice.base_service import BaseLLMService
from llmservice.schemas import GenerationRequest, GenerationResult


class MyLLMService(BaseLLMService):
    """Concrete wrapper with one useful async method."""
    MODEL = "gpt-4o-mini"

    async def capital_async(self, country: str) -> GenerationResult:
        prompt = f"bring me the capital of this country: {country}"
        req = GenerationRequest(formatted_prompt=prompt, model=self.MODEL)
        return await self.execute_generation_async(req)


async def bench_concurrency(n: int = 20, country: str = "Turkey") -> None:
    svc = MyLLMService(
        show_logs=False,
        max_concurrent_requests=n,   # semaphore size
        max_rpm=None,                # disable gates unless you want to test them
        max_tpm=None,
    )

    t0 = time.perf_counter()
    # Fire n concurrent awaits
    results: List[GenerationResult] = await asyncio.gather(
        *(svc.capital_async(country) for _ in range(n))
    )
    wall = time.perf_counter() - t0

    # Extract per-call latency and success flags
    lats   = [r.total_invoke_duration_ms for r in results]
    failed = [r for r in results if not r.success]

    print(f"\n=== {n} concurrent calls ===")
    print(f"wall-clock elapsed      : {wall:6.3f} s")
    print(f"per-call μ latency      : {statistics.mean(lats):7.1f} ms")
    print(f"per-call σ latency      : {statistics.pstdev(lats):7.1f} ms")
    print(f"min | median | max      : {min(lats):.1f} | "
          f"{statistics.median(lats):.1f} | {max(lats):.1f} ms")
    print(f"failures                : {len(failed)}/{n}\n")


if __name__ == "__main__":
    # optional CLI arg: python -m llmservice.bench_concurrency 50
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    asyncio.run(bench_concurrency(N))
