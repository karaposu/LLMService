from abc import ABC
from llmservice.generation_engine import GenerationEngine, GenerationRequest, GenerationResult
from llmservice.usage_stats import UsageStats
import logging
from typing import Optional, Union

class BaseLLMService(ABC):
    def __init__(self, logger: Optional[logging.Logger] = None, model_name: str = "default-model", yaml_file_path: Optional[str] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.generation_engine = GenerationEngine(logger=self.logger, model_name=model_name)
        self.usage_stats = UsageStats()
        self.request_id_counter = 0

        if yaml_file_path:
            self.load_prompts(yaml_file_path)
        else:
            self.logger.warning("No prompts yaml file provided.")

    def _generate_request_id(self) -> int:
        """Generates a unique request ID."""
        self.request_id_counter += 1
        return self.request_id_counter

    def _store_usage(self, generation_result: GenerationResult):
        """Stores usage statistics from the generation result."""
        if generation_result and generation_result.meta:
            self.usage_stats.update(generation_result.meta)
            operation_name = generation_result.operation_name or "unknown_operation"
            request_id = generation_result.request_id
            self.logger.info(
                f"Operation: {operation_name}, Request ID: {request_id}, "
                f"Input Tokens: {generation_result.meta.get('input_tokens', 0)}, "
                f"Output Tokens: {generation_result.meta.get('output_tokens', 0)}, "
                f"Total Cost: ${generation_result.meta.get('total_cost', 0):.5f}"
            )

    def execute_generation(
        self,
        generation_request: GenerationRequest,
        operation_name: Optional[str] = None
    ) -> GenerationResult:
        """Executes the generation and stores usage statistics."""
        generation_request.operation_name = operation_name or generation_request.operation_name
        generation_request.request_id = generation_request.request_id or self._generate_request_id()

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
        # Assign operation name and request ID
        generation_request.operation_name = operation_name or generation_request.operation_name
        generation_request.request_id = generation_request.request_id or self._generate_request_id()

        # Perform the asynchronous generation
        generation_result = await self.generation_engine.generate_output_async(generation_request)

        # Ensure request_id is set in the result
        generation_result.request_id = generation_request.request_id

        # Store usage statistics
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
