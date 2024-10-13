# base_service.py

import logging
import time
import asyncio
from abc import ABC
from collections import deque
from typing import Optional, Union

from llmservice.generation_engine import GenerationEngine, GenerationRequest, GenerationResult
from llmservice.usage_stats import UsageStats


class BaseLLMService(ABC):
    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        model_name: str = "default-model",
        yaml_file_path: Optional[str] = None,
        rpm_window_seconds: int = 60,
        max_rpm: int = 60,
        max_concurrent_requests: int = 5,
    ):
        """
        Base class for LLM services.

        :param logger: Optional logger instance.
        :param model_name: Default model name to use.
        :param yaml_file_path: Path to the YAML file containing prompts.
        :param rpm_window_seconds: Time window in seconds for RPM calculation.
        :param max_rpm: Maximum allowed Requests Per Minute.
        :param max_concurrent_requests: Maximum number of concurrent asynchronous requests.
        """
        self.logger = logger or logging.getLogger(__name__)
        self.generation_engine = GenerationEngine(logger=self.logger, model_name=model_name)
        self.usage_stats = UsageStats(model=model_name)
        self.request_id_counter = 0
        self.request_timestamps = deque()
        self.rpm_window_seconds = rpm_window_seconds
        self.max_rpm = max_rpm
        self.max_concurrent_requests = max_concurrent_requests
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        if yaml_file_path:
            self.load_prompts(yaml_file_path)
        else:
            self.logger.warning("No prompts YAML file provided.")

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
            self.logger.info(
                f"Operation: {operation_name}, Request ID: {request_id}, "
                f"Input Tokens: {generation_result.meta.get('input_tokens', 0)}, "
                f"Output Tokens: {generation_result.meta.get('output_tokens', 0)}, "
                f"Total Cost: ${generation_result.meta.get('total_cost', 0):.5f}"
            )
            # Record the timestamp for RPM calculation
            self.request_timestamps.append(time.time())

            # Clean up old timestamps and log RPM
            self._clean_old_timestamps()
            rpm = self.get_current_rpm()
            self.logger.info(f"Current RPM: {rpm:.2f}")

    def _clean_old_timestamps(self):
        """Removes timestamps older than the RPM window."""
        current_time = time.time()
        while self.request_timestamps and (current_time - self.request_timestamps[0] > self.rpm_window_seconds):
            self.request_timestamps.popleft()

    def get_current_rpm(self) -> float:
        """Calculates the current Requests Per Minute (RPM)."""
        self._clean_old_timestamps()
        rpm = len(self.request_timestamps) * (60 / self.rpm_window_seconds)
        return rpm

    async def _wait_if_rate_limited(self):
        """Waits if the current RPM exceeds the maximum allowed RPM."""
        while self.get_current_rpm() >= self.max_rpm:
            wait_time = self.rpm_window_seconds - (time.time() - self.request_timestamps[0])
            wait_time = max(wait_time, 0)
            self.logger.warning(f"Rate limit reached. Waiting for {wait_time:.2f} seconds.")
            await asyncio.sleep(wait_time)
            self._clean_old_timestamps()

    def execute_generation(
        self,
        generation_request: GenerationRequest,
        operation_name: Optional[str] = None
    ) -> GenerationResult:
        """Executes the generation synchronously and stores usage statistics."""
        generation_request.operation_name = operation_name or generation_request.operation_name
        generation_request.request_id = generation_request.request_id or self._generate_request_id()

        # Rate limiting check (for synchronous calls, we can't wait asynchronously)
        if self.get_current_rpm() >= self.max_rpm:
            self.logger.error("Rate limit exceeded. Cannot proceed with synchronous execution.")
            raise Exception("Rate limit exceeded.")

        generation_result = self.generation_engine.generate_output(generation_request)
        generation_result.request_id = generation_request.request_id
        self._store_usage(generation_result)
        return generation_result

    async def execute_generation_async(
        self,
        generation_request: GenerationRequest,
        operation_name: Optional[str] = None
    ) -> GenerationResult:
        """Asynchronously executes the generation and stores usage statistics."""
        # Rate limiting check
        await self._wait_if_rate_limited()

        async with self.semaphore:
            generation_request.operation_name = operation_name or generation_request.operation_name
            generation_request.request_id = generation_request.request_id or self._generate_request_id()

            generation_result = await self.generation_engine.generate_output_async(generation_request)
            generation_result.request_id = generation_request.request_id
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
