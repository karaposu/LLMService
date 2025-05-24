# base_service.py

import logging
import time
import asyncio
from abc import ABC
from typing import Optional, Union

from llmservice.generation_engine import GenerationEngine, GenerationRequest, GenerationResult
from llmservice.schemas import UsageStats
from collections import deque


class BaseLLMService(ABC):
    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        default_model_name: str = "default-model",
        yaml_file_path: Optional[str] = None,
        rpm_window_seconds: int = 60,
        max_rpm: int = 60,
        max_tpm: int | None = None,         # ❶  optional cap
        max_concurrent_requests: int = 5,
        default_number_of_retries: int = 2,
        show_logs=False
    ):
        """
        Base class for LLM services.

        :param logger: Optional logger instance.
        :param default_model_name: Default model name to use.
        :param yaml_file_path: Path to the YAML file containing prompts.
        :param rpm_window_seconds: Time window in seconds for RPM calculation.
        :param max_rpm: Maximum allowed Requests Per Minute.
        :param max_concurrent_requests: Maximum number of concurrent asynchronous requests.
        """
        self.logger = logger or logging.getLogger(__name__)
        self.generation_engine = GenerationEngine( model_name=default_model_name)
        self.usage_stats = UsageStats(model=default_model_name)
        self.request_id_counter = 0
        self.request_timestamps = deque()
        self.rpm_window_seconds = rpm_window_seconds
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.max_concurrent_requests = max_concurrent_requests
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        self.default_number_of_retries=default_number_of_retries
        self.show_logs=show_logs

        # self.token_timestamps = deque() 
        self.token_timestamps: deque[tuple[float, int]] = deque()       

        if yaml_file_path:
            self.load_prompts(yaml_file_path)
        else:
            self.logger.warning("No prompts YAML file provided.")


    def set_rate_limits(
            self,
            *,
            max_rpm: Optional[int] = None,
            max_tpm: Optional[int] = None
        ) -> None:
            """Configure RPM/TPM caps."""
            if max_rpm is not None:
                self.max_rpm = max_rpm
            if max_tpm is not None:
                self.max_tpm = max_tpm

    def set_concurrency(self, max_concurrent_requests: int) -> None:
        """Configure max simultaneous async requests."""
        self.max_concurrent_requests = max_concurrent_requests
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)


    def _clean_old_token_timestamps(self):
        now = time.time()
        self.token_timestamps = deque(
            (ts, tok) for ts, tok in self.token_timestamps
            if now - ts <= self.rpm_window_seconds
        )

    def _wait_if_token_limited_sync(self) -> None:
        """Block the current thread until TPM drops below max_tpm (sync version)."""
        if self.max_tpm is None:
            return  # no TPM cap

        while self.get_current_tpm() >= self.max_tpm:
            oldest_ts, _ = self.token_timestamps[0]
            sleep_for = self.rpm_window_seconds - (time.time() - oldest_ts)
            sleep_for = max(sleep_for, 0)
            self.logger.warning(
                f"TPM cap reached ({self.max_tpm}). Sleeping {sleep_for:.2f}s (sync)."
            )
            time.sleep(sleep_for)
            self._clean_old_token_timestamps()

    
    async def _wait_if_token_limited(self) -> None:
        """Pause until tokens-per-minute drops below `max_tpm`."""
        if self.max_tpm is None:
            return  # TPM throttling disabled
        
        while self.get_current_tpm() >= self.max_tpm:
            oldest_ts, _ = self.token_timestamps[0]
            sleep_for = self.rpm_window_seconds - (time.time() - oldest_ts)
            sleep_for = max(sleep_for, 0)
            self.logger.warning(
                f"TPM cap reached ({self.max_tpm}). Sleeping {sleep_for:.2f}s."
            )
            await asyncio.sleep(sleep_for)
            self._clean_old_token_timestamps()

    def get_current_tpm(self) -> float:
        """Sum of tokens in the last RPM window (i.e. TPM)."""
        self._clean_old_token_timestamps()
        total = sum(tokens for _, tokens in self.token_timestamps)
        # scale if window ≠ 60 s
        return total * (60 / self.rpm_window_seconds)

    def _generate_request_id(self) -> int:
        """Generates a unique request ID."""
        self.request_id_counter += 1
        return self.request_id_counter

    def _store_usage(self, generation_result: GenerationResult):
        """Stores usage statistics from the generation result."""
        if generation_result and generation_result.meta:
            operation_name = generation_result.operation_name or "unknown_operation"
            # Update usage stats with operation name
            self.usage_stats.update(generation_result.meta, operation_name)
            # Log the operation name and request ID
            request_id = generation_result.request_id

            if  self.show_logs:
                self.logger.info( f"Operation: {operation_name}, Request ID: {request_id} ")
                self.logger.info( f"Input Tokens: {generation_result.meta.get('input_tokens', 0)}, Output Tokens: {generation_result.meta.get('output_tokens', 0)} ")
                self.logger.info(f"Total Cost: ${generation_result.meta.get('total_cost', 0):.5f} ")


            # self.logger.info(
            #     f"Operation: {operation_name}, Request ID: {request_id}, "
            #     f"Input Tokens: {generation_result.meta.get('input_tokens', 0)}, "
            #     f"Output Tokens: {generation_result.meta.get('output_tokens', 0)}, "
            #     f"Total Cost: ${ generation_result.meta.get('total_cost', 0):.5f }"
            # )
            # Record the timestamp for RPM calculation
            timestamp = time.time()
            self.request_timestamps.append(timestamp)
            
            # track tokens-per-minute
            total_tokens = generation_result.meta.get('total_tokens', 0)
            self.token_timestamps.append((timestamp, total_tokens))
            self._clean_old_token_timestamps()       

            # Clean up old timestamps and log RPM
            self._clean_old_timestamps()
            rpm = self.get_current_rpm()
            if self.show_logs:
                self.logger.info(f"Current RPM: {rpm:.2f}")

    def _clean_old_timestamps(self):
        """Remove any timestamps older than the RPM window."""
        now = time.time()
        self.request_timestamps = deque(
            ts for ts in self.request_timestamps
            if now - ts <= self.rpm_window_seconds
        )

    def get_current_rpm(self) -> float:
        """Calculates the current Requests Per Minute (RPM)."""
        self._clean_old_timestamps()
        rpm = len(self.request_timestamps) * (60 / self.rpm_window_seconds)
        return rpm

    

    def execute_generation(
        self,
        generation_request: GenerationRequest,
        operation_name: Optional[str] = None
    ) -> GenerationResult:
        """Executes the generation synchronously and stores usage statistics."""
        generation_request.operation_name = operation_name or generation_request.operation_name
        generation_request.request_id = generation_request.request_id or self._generate_request_id()


         # Wait (not raise) on RPM
        self._wait_if_rate_limited_sync()

        # Wait on TPM
        self._wait_if_token_limited_sync()

        # # Rate limiting check (for synchronous calls, we can't wait asynchronously)
        # if self.get_current_rpm() >= self.max_rpm:
        #     self.logger.error("Rate limit exceeded. Cannot proceed with synchronous execution.")
        #     raise Exception("Rate limit exceeded.")
        # if self.max_tpm is not None and self.get_current_tpm() >= self.max_tpm:
        #     raise Exception("TPM cap exceeded (sync call).")

        generation_result = self.generation_engine.generate_output(generation_request)
        generation_result.request_id = generation_request.request_id
        self._store_usage(generation_result)
        return generation_result
    
    async def _wait_if_rate_limited(self):
        """Wait until RPM drops below the max_rpm threshold."""
        while self.get_current_rpm() >= self.max_rpm:
            # Time until the oldest timestamp exits the window
            wait_time = self.rpm_window_seconds - (time.time() - self.request_timestamps[0])
            wait_time = max(wait_time, 0)
            self.logger.warning(f"Rate limit reached. Waiting {wait_time:.2f}s.")
            await asyncio.sleep(wait_time)
            self._clean_old_timestamps()

    def _wait_if_rate_limited_sync(self) -> None:
        """Block until RPM drops below max_rpm (synchronous path)."""
        while self.get_current_rpm() >= self.max_rpm:
            oldest_ts = self.request_timestamps[0]
            sleep_for = self.rpm_window_seconds - (time.time() - oldest_ts)
            sleep_for = max(sleep_for, 0)
            self.logger.warning(
                f"RPM cap reached ({self.max_rpm}). Sleeping {sleep_for:.2f}s (sync)."
            )
            time.sleep(sleep_for)
            self._clean_old_timestamps()

    async def execute_generation_async(
        self,
        generation_request: GenerationRequest,
        operation_name: Optional[str] = None
    ) -> GenerationResult:
        generation_request.operation_name = operation_name or generation_request.operation_name
        generation_request.request_id = (
            generation_request.request_id or self._generate_request_id()
        )

        # # ← This call ensures you don’t exceed max_rpm
        await self._wait_if_rate_limited()
        await self._wait_if_token_limited()

        async with self.semaphore:
            generation_result = await self.generation_engine.generate_output_async(generation_request)
            self._store_usage(generation_result)
            return generation_result


    def load_prompts(self, yaml_file_path: str):
        """Loads prompts from a YAML file."""
        self.generation_engine.load_prompts(yaml_file_path)

    # Additional methods for usage stats
    def get_usage_stats(self) -> dict:
        """Returns the current usage statistics as a dictionary."""
        return self.usage_stats.to_dict()

    def reset_usage_stats(self):
        """Resets the usage statistics."""
        self.usage_stats = UsageStats(model=self.generation_engine.llm_handler.model_name)

        # Also reset request timestamps
        self.request_timestamps.clear()
