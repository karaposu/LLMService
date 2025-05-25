# llmservice/base_service.py
"""
Core service orchestration + optional live metrics.

The class now relies on `MetricsRecorder` for:
    • request/response counters
    • RPM / RePM / TPM
    • cumulative cost
"""

from __future__ import annotations

import asyncio
    
import logging
import time
from abc import ABC
from collections import deque
from typing import Optional

from llmservice.generation_engine import GenerationEngine, GenerationRequest, GenerationResult
from llmservice.live_metrics import MetricsRecorder        # ← NEW
from llmservice.schemas import UsageStats


class BaseLLMService(ABC):
    # --------------------------------------------------------------------- #
    #  Construction
    # --------------------------------------------------------------------- #
    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
        default_model_name: str = "default-model",
        yaml_file_path: Optional[str] = None,
        rpm_window_seconds: int = 60,
        max_rpm: int = 60,
        max_tpm: int | None = None,
        max_concurrent_requests: int = 5,
        default_number_of_retries: int = 2,
        enable_metrics_logging: bool = False,
        metrics_log_interval: float = 0.1,
        show_logs: bool = False
    ) -> None:

        # ---- core objects ----
        self.logger         = logger or logging.getLogger(__name__)
        self.generation_engine = GenerationEngine(model_name=default_model_name)
        self.usage_stats    = UsageStats(model=default_model_name)

        # ---- metrics ----
        self.metrics = MetricsRecorder(
            window=rpm_window_seconds,
            max_rpm=max_rpm,
            max_tpm=max_tpm
        )

   

        self.request_id_counter    = 0
        self.semaphore             = asyncio.Semaphore(max_concurrent_requests)
        self.default_number_of_retries = default_number_of_retries
        self.show_logs             = show_logs

        # ---- optional background logger ----
        self._metrics_logger = logging.getLogger("llmservice.metrics")
        if enable_metrics_logging:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            loop.create_task(self._emit_metrics(metrics_log_interval))

        # ---- load prompt YAML (optional) ----
        if yaml_file_path:
            self.load_prompts(yaml_file_path)
        else:
            self.logger.warning("No prompts YAML file provided.")

    # ------------------------------------------------------------------ #
    #  Convenience: file logging for metrics
    # ------------------------------------------------------------------ #
    # def setup_metrics_log_file(
    #     self,
    #     path: str,
    #     *,
    #     level: int = logging.INFO,
    #     fmt: str = "%(asctime)s %(message)s",
    #     datefmt: str = "%Y-%m-%d %H:%M:%S"
    # ) -> None:
    #     handler   = logging.FileHandler(path)
    #     formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
    #     handler.setFormatter(formatter)

    #     self._metrics_logger.addHandler(handler)
    #     self._metrics_logger.setLevel(level)
    #     self._metrics_logger.propagate = False      # avoid duplicates

    # ------------------------------------------------------------------ #
    #  ID helpers
    # ------------------------------------------------------------------ #
    def _generate_request_id(self) -> int:
        self.request_id_counter += 1
        return self.request_id_counter

    # ------------------------------------------------------------------ #
    #  Rate-limit waits
    # ------------------------------------------------------------------ #
    async def _wait_if_rate_limited(self) -> None:
        while self.metrics.is_rpm_limited():
            wait_for = self._secs_until_window_refresh(self.metrics.sent_ts)
            self.logger.warning(f"RPM cap reached. Sleeping {wait_for:.2f}s.")
            await asyncio.sleep(wait_for)

    def _wait_if_rate_limited_sync(self) -> None:
        while self.metrics.is_rpm_limited():
            wait_for = self._secs_until_window_refresh(self.metrics.sent_ts)
            self.logger.warning(f"RPM cap reached. Sleeping {wait_for:.2f}s (sync).")
            time.sleep(wait_for)

    async def _wait_if_token_limited(self) -> None:
        while self.metrics.is_tpm_limited():
            wait_for = self._secs_until_window_refresh(self.metrics.tok_ts, is_pair=True)
            self.logger.warning(f"TPM cap reached. Sleeping {wait_for:.2f}s.")
            await asyncio.sleep(wait_for)

    def _wait_if_token_limited_sync(self) -> None:
        while self.metrics.is_tpm_limited():
            wait_for = self._secs_until_window_refresh(self.metrics.tok_ts, is_pair=True)
            self.logger.warning(f"TPM cap reached. Sleeping {wait_for:.2f}s (sync).")
            time.sleep(wait_for)

    # helper
    def _secs_until_window_refresh(self, dq: deque, *, is_pair=False) -> float:
        if not dq:
            return 0
        oldest = dq[0][0] if is_pair else dq[0]
        return max(0.0, self.metrics.window - (time.time() - oldest))

    # ------------------------------------------------------------------ #
    #  Generation entry points
    # ------------------------------------------------------------------ #
    def execute_generation(
        self,
        generation_request: GenerationRequest,
        operation_name: Optional[str] = None
    ) -> GenerationResult:

        generation_request.operation_name = operation_name or generation_request.operation_name
        generation_request.request_id     = generation_request.request_id or self._generate_request_id()

        self._wait_if_rate_limited_sync()
        self._wait_if_token_limited_sync()
       
        # self.metrics.mark_sent()        
        self.metrics.mark_sent(generation_request.request_id)                              #

        result = self.generation_engine.generate_output(generation_request)
        self._after_response(result)
        return result

    async def execute_generation_async(
        self,
        generation_request: GenerationRequest,
        operation_name: Optional[str] = None
    ) -> GenerationResult:

        generation_request.operation_name = operation_name or generation_request.operation_name
        generation_request.request_id     = generation_request.request_id or self._generate_request_id()

        await self._wait_if_rate_limited()
        await self._wait_if_token_limited()
      
       
        # self.metrics.mark_sent()                             # ← SENT
        self.metrics.mark_sent(generation_request.request_id)  

        async with self.semaphore:
            result = await self.generation_engine.generate_output_async(generation_request)
            self._after_response(result)
            return result

    # ------------------------------------------------------------------ #
    #  After-response bookkeeping
    # ------------------------------------------------------------------ #
    def _after_response(self, generation_result: GenerationResult) -> None:
        # ---- metrics ----
        tokens = generation_result.meta.get("total_tokens", 0)
        cost   = generation_result.meta.get("total_cost",   0.0)

        # ------------ atomic metrics update ------------
        # with self._metrics_lock:
        #     self.metrics.mark_rcv(tokens=tokens, cost=cost)    # ← RECEIVED
        # self.metrics.mark_rcv(tokens=tokens, cost=cost)    # ← RECEIVED
        self.metrics.mark_rcv(generation_result.request_id,
                      tokens=tokens, cost=cost) 
    
        
        # ---- aggregate per-operation usage ----
        op_name = generation_result.operation_name or "unknown_operation"
        self.usage_stats.update(generation_result.meta, op_name)

        # ---- optional verbose log ----
        if self.show_logs:
            self.logger.info(
                f"Op:{op_name} ReqID:{generation_result.request_id} "
                f"InTok:{generation_result.meta.get('input_tokens',0)} "
                f"OutTok:{generation_result.meta.get('output_tokens',0)} "
                f"Cost:${cost:.5f}"
            )

    # ------------------------------------------------------------------ #
    #  Metrics emission loop
    # ------------------------------------------------------------------ #
    async def _emit_metrics(self, every: float):
        while True:
            snap = self.metrics.snapshot()
            self._metrics_logger.info(
                f"TotalReq:{snap.total_sent}  TotalRcv:{snap.total_rcv}  "
                f"RPM:{snap.rpm:.0f}/{self.metrics.max_rpm or '∞'}  "
                f"RePM:{snap.repm:.0f}  "
                f"TPM:{snap.tpm:.0f}/{self.metrics.max_tpm or '∞'}  "
                f"Cost:${snap.cost:.5f}"
            )
            await asyncio.sleep(every)

    # ------------------------------------------------------------------ #
    #  Public helpers
    # ------------------------------------------------------------------ #
    def load_prompts(self, yaml_file_path: str) -> None:
        self.generation_engine.load_prompts(yaml_file_path)

    def get_usage_stats(self) -> dict:
        return self.usage_stats.to_dict()

    def get_total_cost(self) -> float:
        return self.metrics.total_cost

    def reset_usage_stats(self) -> None:
        self.usage_stats  = UsageStats(model=self.generation_engine.llm_handler.model_name)
        self.metrics      = MetricsRecorder(window=self.metrics.window,
                                            max_rpm=self.metrics.max_rpm,
                                            max_tpm=self.metrics.max_tpm)
        

    # ------------------------------------------------------------------ #
    #  Runtime re-configuration helpers  (optional)
    # ------------------------------------------------------------------ #
    def set_rate_limits(
        self,
        *,
        max_rpm: int | None = None,
        max_tpm: int | None = None
    ) -> None:
        """Change RPM / TPM caps on the fly."""
        if max_rpm is not None:
            self.metrics.max_rpm = max_rpm
        if max_tpm is not None:
            self.metrics.max_tpm = max_tpm

    def set_concurrency(self, max_concurrent_requests: int) -> None:
        """Adjust the async semaphore for new parallelism."""
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)


    # ------------------------------------------------------------------ #
    #  Legacy metric accessors (delegate to MetricsRecorder)
    # ------------------------------------------------------------------ #
    def get_current_rpm(self) -> float:
        """Requests-per-minute (sent)."""
        return self.metrics.rpm()

    def get_current_repmin(self) -> float:
        """Responses-per-minute (received)."""
        return self.metrics.repm()

    def get_current_tpm(self) -> float:
        """Tokens-per-minute (received)."""
        return self.metrics.tpm()

