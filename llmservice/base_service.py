# llmservice/base_service.py
"""
Core service orchestration + optional live metrics.

The class now relies on `MetricsRecorder` for:
    • request/response counters
    • RPM / RePM / TPM
    • cumulative cost
"""

 # to run   python -m llmservice.base_service

from __future__ import annotations

import asyncio
    
import logging
import time
from abc import ABC
from collections import deque
from typing import Optional, Tuple

from llmservice.generation_engine import GenerationEngine, GenerationRequest, GenerationResult
from llmservice.live_metrics import MetricsRecorder        # ← NEW
from llmservice.schemas import UsageStats, EventTimestamps  # ← FIXED: Added EventTimestamps import
from .utils import _now_dt
import uuid, time, asyncio
from llmservice.gates import RpmGate,TpmGate
from llmservice.debug_tools import timed 





# from . import prompts
# import inspect

# class MyLLMService(BaseLLMService):
#     ...

#     # ── internal helper ──────────────────────────────────────────
#     def _render_prompt(
#         self,
#         template_name: str | None,
#         *,
#         corpus: str,
#         thing: str
#     ) -> str:
#         """
#         Return the final prompt text.

#         • `template_name` is the UPPER-case constant name in prompts.py
#           (case-insensitive).  
#         • If the name is None or unknown, FALLS BACK to FILTER_BASE.
#         • Automatically fills `{corpus}` and `{thing}` placeholders.
#         """
#         # collect all upper-case string constants
#         prompt_map = {
#             k.upper(): v
#             for k, v in inspect.getmembers(prompts)
#             if isinstance(v, str) and k.isupper()
#         }

#         raw_tpl = prompt_map.get(
#             (template_name or "").upper(),
#             prompts.FILTER_BASE
#         )

#         # one central place that does the .format()
#         return raw_tpl.format(corpus=corpus, thing=thing)


class BaseLLMService(ABC):
  
    
    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
        default_model_name: str = "default-model",
        rpm_window_seconds: int = 60,
        max_rpm: int = 100,
        max_tpm: int | None = None,
        max_concurrent_requests: int = 100,
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

        self._rpm_gate = RpmGate(window_seconds=rpm_window_seconds, logger=self.logger)
        self._tpm_gate = TpmGate(window_seconds=rpm_window_seconds, logger=self.logger)

        # ---- optional background logger ----
        self._metrics_logger = logging.getLogger("llmservice.metrics")
        if enable_metrics_logging:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            loop.create_task(self._emit_metrics(metrics_log_interval))

    
    # ------------------------------------------------------------------ #
    #  ID helpers
    # ------------------------------------------------------------------ #
    def _generate_request_id(self) -> int:
        self.request_id_counter += 1
        return self.request_id_counter


    def _new_trace_id(self) -> str:
        return str(uuid.uuid4())

    # ------------------------------------------------------------------ #
    #  Generation entry points
    # ------------------------------------------------------------------ #

    def execute_generation(
        self,
        generation_request: GenerationRequest,
        operation_name: Optional[str] = None
    ) -> GenerationResult:
        
        trace_id = self._new_trace_id() 
        
        # 1) Take a "before" snapshot of RPM/TPM
        rpm_before = None
        tpm_before = None
        rpm_after = None
        tpm_after = None
       
        try:
            rpm_before = self.get_current_rpm()
            tpm_before = self.get_current_tpm()
        except Exception:
            # If metrics object isn't set up yet, default to None
            rpm_before = None
            tpm_before = None

        # Set request metadata (but NOT trace_id since it's not in the schema)
        generation_request.operation_name = operation_name or generation_request.operation_name
        generation_request.request_id     = generation_request.request_id or self._generate_request_id()
        # ← FIXED: Removed problematic line: generation_request.trace_id=trace_id

        # 4) Now we are about to enter any rate‐limit / concurrency waits …
        #    At this very moment, we consider the request "enqueued."
        #    (It may still have to wait on RPM or TPM checks, etc.)
        generation_enqueued_at = _now_dt()

        rpm_waited, rpm_wait_loops, rpm_waited_ms = self._rpm_gate.wait_if_rate_limited_sync(self.metrics)
        tpm_waited, tpm_wait_loops, tpm_waited_ms = self._tpm_gate.wait_if_token_limited_sync(self.metrics)
        
        # 6) Immediately before calling the LLM, we are "dequeued." 
        generation_dequeued_at = _now_dt()

        self.metrics.mark_sent(trace_id)      
        
        result = self.generation_engine.generate_output(generation_request)

        result.trace_id = trace_id  # ← This is fine - assigning TO result, not FROM request

        result.backoff.rpm_loops = rpm_wait_loops
        result.backoff.rpm_ms    = rpm_waited_ms
        result.backoff.tpm_loops = tpm_wait_loops
        result.backoff.tpm_ms    = tpm_waited_ms

        result.total_backoff_ms= result.backoff.total_ms

        if not result.success:
            self.metrics.unmark_sent(trace_id)
    
        self._after_response(result)

        try:
            rpm_after = self.get_current_rpm()
            tpm_after = self.get_current_tpm()
        except Exception:
            rpm_after = None
            tpm_after = None

        result.rpm_at_the_end= rpm_after
        result.rpm_at_the_beginning= rpm_before
        result.tpm_at_the_end= tpm_after
        result.tpm_at_the_beginning= tpm_before

        # ← FIXED: Add null safety for timestamps
        if result.timestamps is None:
            result.timestamps = EventTimestamps()
        result.timestamps.generation_enqueued_at  = generation_enqueued_at
        result.timestamps.generation_dequeued_at  = generation_dequeued_at

        result.rpm_waited=rpm_waited
        result.rpm_wait_loops=rpm_wait_loops
        result.rpm_waited_ms=rpm_waited_ms

        result.tpm_waited=tpm_waited
        result.tpm_wait_loops=tpm_wait_loops
        result.tpm_waited_ms=tpm_waited_ms

        return result
    

    async def execute_generation_async(
        self,
        generation_request: GenerationRequest,
        operation_name: Optional[str] = None
    ) -> GenerationResult:
        
        trace_id = self._new_trace_id() 

        # 1) Take a "before" snapshot of RPM/TPM
        rpm_before = None
        tpm_before = None
        rpm_after = None
        tpm_after = None
       
        try:
            rpm_before = self.get_current_rpm()
            tpm_before = self.get_current_tpm()
        except Exception:
            # If metrics object isn't set up yet, default to None
            rpm_before = None
            tpm_before = None
        
        generation_request.operation_name = operation_name or generation_request.operation_name
        generation_request.request_id     = generation_request.request_id or self._generate_request_id()
        # ← FIXED: Removed problematic line: generation_request.trace_id=trace_id

        # 4) We're about to enter any rate‐limit or concurrency wait → "enqueued"
        generation_enqueued_at = _now_dt()
    
        rpm_waited, rpm_wait_loops, rpm_waited_ms = await self._rpm_gate.wait_if_rate_limited(self.metrics)
        tpm_waited, tpm_wait_loops, tpm_waited_ms = await self._tpm_gate.wait_if_token_limited(self.metrics)

        # 6) Now wait on the concurrency semaphore before calling the LLM
        generation_dequeued_at = _now_dt()

        async with self.semaphore:
            self.metrics.mark_sent(trace_id)
            result = await self.generation_engine.generate_output_async(generation_request)
            result.trace_id = trace_id  # ← This is fine - assigning TO result, not FROM request
            
            if not result.success:
                self.metrics.unmark_sent(trace_id)
            self._after_response(result)

            try:
                rpm_after = self.get_current_rpm()
                tpm_after = self.get_current_tpm()
            except Exception:
                rpm_after = None
                tpm_after = None

            result.rpm_at_the_end= rpm_after
            result.rpm_at_the_beginning= rpm_before
            result.tpm_at_the_end= tpm_after
            result.tpm_at_the_beginning= tpm_before

            result.backoff.rpm_loops = rpm_wait_loops
            result.backoff.rpm_ms    = rpm_waited_ms
            result.backoff.tpm_loops = tpm_wait_loops
            result.backoff.tpm_ms    = tpm_waited_ms

            result.total_backoff_ms= result.backoff.total_ms

            # ← FIXED: Add null safety for timestamps
            if result.timestamps is None:
                result.timestamps = EventTimestamps()
            result.timestamps.generation_enqueued_at  = generation_enqueued_at
            result.timestamps.generation_dequeued_at  = generation_dequeued_at

            result.rpm_waited=rpm_waited
            result.rpm_wait_loops=rpm_wait_loops
            result.rpm_waited_ms=rpm_waited_ms

            result.tpm_waited=tpm_waited
            result.tpm_wait_loops=tpm_wait_loops
            result.tpm_waited_ms=tpm_waited_ms

            return result

    # ------------------------------------------------------------------ #
    #  After-response bookkeeping
    # ------------------------------------------------------------------ #
    def _after_response(self, generation_result: GenerationResult) -> None:
        # ---- metrics ----
        tokens = generation_result.usage.get("total_tokens", 0)
        cost   = generation_result.usage.get("total_cost",   0.0)

        self.metrics.mark_rcv(generation_result.trace_id, tokens=tokens, cost=cost) 
        
        # ---- aggregate per-operation usage ----
        op_name = generation_result.operation_name or "unknown_operation"
        self.usage_stats.update(generation_result.usage, op_name)

        # ---- optional verbose log ----
        if self.show_logs:
            self.logger.info(
                f"Op:{op_name} ReqID:{generation_result.request_id} "
                f"InTok:{generation_result.usage.get('input_tokens',0)} "
                f"OutTok:{generation_result.usage.get('output_tokens',0)} "
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



# Main function for testing
def main():

    class MyLLMService(BaseLLMService):
    
        def ask_llm_to_tell_capital(self,user_input: str,) -> GenerationResult:
            
            prompt= f"bring me the capital of this country: {user_input}"
            generation_request = GenerationRequest(
                user_prompt=prompt,
                model="gpt-4o-mini",  
                # model="gpt-4.1-nano",  
            )
            generation_result = self.execute_generation(generation_request)
            return generation_result
        
        
        def bring_only_capital(self,user_input: str,) -> GenerationResult:

            prompt= f"bring me the capital of this {user_input}"
            
            pipeline_config = [
                {
                    'type': 'SemanticIsolation',   # uses LLMs to isolate specific part of the answer.
                    'params': {
                        'semantic_element_for_extraction': 'just the capital'
                    }
                }
            ]
            generation_request = GenerationRequest(
                user_prompt=prompt,
                model="gpt-4o-mini",  # Use the model specified in __init__
                pipeline_config=pipeline_config,
            )

            # Execute the generation synchronously
            generation_result = self.execute_generation(generation_request)
            return generation_result

        # NEW: Test audio functionality through the service
        def generate_audio_response(self, text_prompt: str) -> GenerationResult:
            """Generate both text and audio response."""
            generation_request = GenerationRequest(
                user_prompt=text_prompt,
                model="gpt-4o-audio-preview",
                output_data_format="both",
                audio_output_config={"voice": "alloy", "format": "wav"}
            )
            return self.execute_generation(generation_request)


    llmservice= MyLLMService()
    our_input= "Turkey"

    generation_result =llmservice.ask_llm_to_tell_capital(our_input)
    print("")
    print(generation_result)

    print("")

    # Test the new audio functionality
    print("\n=== Testing Audio Through Service ===")
    try:
        audio_result = llmservice.generate_audio_response("Tell me a short joke")
        print(f"Audio Success: {audio_result.success}")
        if audio_result.success and audio_result.save_audio("llmservice/service_test_audio.wav"):
            print("✅ Audio saved through service!")
            audio_data = audio_result.get_audio_data()
            if audio_data:
                print(f"Audio size: {len(audio_data)} bytes")
            transcript = audio_result.get_audio_transcript()
            if transcript:
                print(f"Audio transcript: {transcript}")
    except Exception as e:
        print(f"Audio test failed: {e}")


if __name__ == '__main__':
    main()