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
        enable_metrics_logging: bool = False,
        metrics_log_interval: float = 0.1,
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
        self.total_requests_sent     = 0
        self.total_responses_rcv     = 0

        self.logger = logger or logging.getLogger(__name__)
        self.generation_engine = GenerationEngine( model_name=default_model_name)
        self.usage_stats = UsageStats(model=default_model_name)
        self.request_id_counter = 0
        self.request_timestamps = deque()
        self.response_timestamps: deque[float] = deque()
        self.rpm_window_seconds = rpm_window_seconds
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.max_concurrent_requests = max_concurrent_requests
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        self.default_number_of_retries=default_number_of_retries
        self.show_logs=show_logs

        # self.token_timestamps = deque() 
        self.token_timestamps: deque[tuple[float, int]] = deque()    

        self._metrics_logger = logging.getLogger("llmservice.metrics")
        if enable_metrics_logging:
            # start the background metrics task
            #asyncio.create_task(self._log_metrics_loop(metrics_log_interval))   
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()  # gets the current (not-yet-running) loop
            loop.create_task(self._log_metrics_loop(metrics_log_interval)) 
            # tail -f llm_metrics.log


        if yaml_file_path:
            self.load_prompts(yaml_file_path)
        else:
            self.logger.warning("No prompts YAML file provided.")

    def _mark_response_received(self):
        now = time.time()
        self.total_responses_rcv += 1
        self.response_timestamps.append(now)
        cutoff = now - self.rpm_window_seconds
        while self.response_timestamps and self.response_timestamps[0] < cutoff:
            self.response_timestamps.popleft()

    def get_current_repmin(self) -> float:
        """
        Responses-per-minute (RePM) over the same sliding window used for RPM.
        """
        cutoff = time.time() - self.rpm_window_seconds
        while self.response_timestamps and self.response_timestamps[0] < cutoff:
            self.response_timestamps.popleft()

        return len(self.response_timestamps) * (60 / self.rpm_window_seconds)

    


    # base_service.py  – inside BaseLLMService
    def _mark_request_sent(self) -> None:
        """Append send-timestamp and trim old ones for RPM accounting."""
        now = time.time()
        self.total_requests_sent += 1
        self.request_timestamps.append(now)
        self._clean_old_timestamps()          # reuse the existing cleaner

    def setup_metrics_log_file(
        self,
        path: str,
        level: int = logging.INFO,
        fmt: str = "%(asctime)s %(message)s",
        datefmt: str = "%Y-%m-%d %H:%M:%S"
    ):
        """
        Attach a FileHandler to the metrics logger so RPM/TPM/Cost are written to `path`.
        The default formatter yields:
        2025-05-25 14:23:01,234 Your log message…

        :param path:         file path to write metrics logs
        :param level:        logging level for the metrics logger
        :param fmt:          log message format (uses %(asctime)s and %(message)s)
        :param datefmt:      timestamp format (strftime style; milliseconds auto-appended)
        """
        handler = logging.FileHandler(path)
        self._metrics_logger.propagate = False
        # note: Python’s logging will append ",mmm" for milliseconds automatically
        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
        handler.setFormatter(formatter)

        self._metrics_logger.addHandler(handler)
        self._metrics_logger.setLevel(level)

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
    
    def get_total_cost(self) -> float:
        """
        Returns the total cost (in dollars) accumulated across all operations
        since the last reset.
        """
        return self.usage_stats.total_usage.get("total_cost", 0.0)
    
    def _store_usage(self, generation_result: GenerationResult) -> None:
        """
        Record usage, token counts and cost *after* a response arrives.
        Assumes `_mark_request_sent()` was already called when the request left.
        """
        if not generation_result or not generation_result.meta:
            return

        # 1) Count the response for RePM / TotalReceived
        self._mark_response_received()

        # 2) Aggregate model-usage metadata
        operation_name = generation_result.operation_name or "unknown_operation"
        self.usage_stats.update(generation_result.meta, operation_name)

        # 3) Track tokens-per-minute
        timestamp     = time.time()
        total_tokens  = generation_result.meta.get("total_tokens", 0)
        self.token_timestamps.append((timestamp, total_tokens))
        self._clean_old_token_timestamps()

        # 4) (Optional) verbose logging
        if self.show_logs:
            in_tok  = generation_result.meta.get("input_tokens", 0)
            out_tok = generation_result.meta.get("output_tokens", 0)
            cost    = generation_result.meta.get("total_cost", 0.0)
            self.logger.info(
                f"Op:{operation_name} ReqID:{generation_result.request_id} "
                f"InTok:{in_tok} OutTok:{out_tok} Cost:${cost:.5f}"
            )



    async def _log_metrics_loop(self, interval: float):
        while True:
            rpm   = self.get_current_rpm()          # sent/min
            repm  = self.get_current_repmin()       # received/min
            tpm   = self.get_current_tpm()
            cost  = self.get_total_cost()

            rpm_str  = f"{rpm:.0f}/{self.max_rpm}"
            tpm_str  = f"{tpm:.0f}/{self.max_tpm or '∞'}"

            self._metrics_logger.info(
                f"TotalRequest: {self.total_requests_sent}   "
                f"TotalReceived: {self.total_responses_rcv}   "
                f"RPM: {rpm_str}   RePM: {repm:.0f}   "
                f"TPM: {tpm_str}   Cost($): {cost:.5f}"
            )
            await asyncio.sleep(interval)

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
        
        self._mark_request_sent()       

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

        self._mark_request_sent()        

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
