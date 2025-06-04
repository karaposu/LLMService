# bench_one.py  ─────────────────────────────────────────────────────────────

# python -m llmservice.bench_one
import asyncio, time, logging, sys
from llmservice.base_service import BaseLLMService
from llmservice.schemas       import GenerationRequest, GenerationResult

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    stream=sys.stdout,
)

# ────────────────────────── your concrete service ─────────────────────────
class MyLLMService(BaseLLMService):

    # ---------- sync ----------
    def bench_method(self, country: str) -> GenerationResult:
        prompt = f"bring me the capital of this country: {country}"
        req = GenerationRequest(formatted_prompt=prompt, model="gpt-4o-mini")
        return self.execute_generation(req)

    # ---------- async ----------
    async def bench_method_async(self, country: str) -> GenerationResult:
        prompt = f"bring me the capital of this country: {country}"
        req = GenerationRequest(formatted_prompt=prompt, model="gpt-4o-mini")
        # IMPORTANT: await the coroutine
        return await self.execute_generation_async(req)


# ────────────────────────── micro-benchmark helper ────────────────────────
def bench_sync(svc: MyLLMService, country: str) -> float:
    t0 = time.perf_counter()
    _  = svc.bench_method(country)
    return time.perf_counter() - t0


async def bench_async(svc: MyLLMService, country: str) -> float:
    t0 = time.perf_counter()
    _  = await svc.bench_method_async(country)
    return time.perf_counter() - t0


# ────────────────────────────── main entry -point ─────────────────────────
if __name__ == "__main__":
    svc         = MyLLMService(show_logs=False)   # <- reuse one instance
    COUNTRY     = "Turkey"

    # synchronous RTT
    sync_dt = bench_sync(svc, COUNTRY)

    # asynchronous RTT (one call)
    async_dt = asyncio.run(bench_async(svc, COUNTRY))

    print(f"\nsync  Δ = {sync_dt:5.3f} s")
    print(f"async Δ = {async_dt:5.3f} s")
