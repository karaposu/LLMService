# llmservice/bench_service.py  ─────────────────────────────────────────────
from llmservice.base_service import BaseLLMService
from llmservice.schemas      import GenerationRequest, GenerationResult

class BenchLLMService(BaseLLMService):
    """
    Each record → two back-to-back completions (lvl-1 then lvl-2),
    mimicking categorize_lvl_by_lvl_async but in a self-contained way.
    """

    MODEL = "gpt-4o-mini"

    # ---- one completion (sync) -----------------------------------------
    def _one_generation_sync(self, seed: str) -> GenerationResult:
        req = GenerationRequest(
            formatted_prompt=f"[sync] dummy prompt {seed}",
            model=self.MODEL,
        )
        return self.execute_generation(req)

    # ---- one completion (async) ----------------------------------------
    async def _one_generation_async(self, seed: str) -> GenerationResult:
        req = GenerationRequest(
            formatted_prompt=f"[async] dummy prompt {seed}",
            model=self.MODEL,
        )
        return await self.execute_generation_async(req)

    # ---- 2-level simulation (sync) -------------------------------------
    def two_lvl_sync(self, seed: str = "x") -> None:
        self._one_generation_sync(f"{seed}-lvl1")
        self._one_generation_sync(f"{seed}-lvl2")

    # ---- 2-level simulation (async) ------------------------------------
    async def two_lvl_async(self, seed: str = "x") -> None:
        await self._one_generation_async(f"{seed}-lvl1")
        await self._one_generation_async(f"{seed}-lvl2")
