# my_llm_service.py

import asyncio
from llmservice.base_service import BaseLLMService
from llmservice.schemas import GenerationRequest, GenerationResult
from typing import Optional, Union


class MyLLMService(BaseLLMService):
    def __init__(self, logger=None, max_concurrent_requests=5):
        super().__init__(
            logger=logger,
            default_model_name="gpt-4o",
            yaml_file_path='prompts.yaml',
            max_rpm=60,
            max_concurrent_requests=max_concurrent_requests,
        )
        # No need for a semaphore here, it's handled in BaseLLMService

    # No need for a semaphore here, it's handled in BaseLLMService

    def translate_to_russian(self, input_paragraph: str,
                             request_id: Optional[Union[str, int]] = None) -> GenerationResult:
        data_for_placeholders = {'input_paragraph': input_paragraph}
        order = ["input_paragraph", "translate_to_russian"]

        # Craft the prompt using the generation engine
        unformatted_prompt = self.generation_engine.craft_prompt(data_for_placeholders, order)

        # Define any postprocessing steps if needed
        pipeline_config = [
            # You can add processing steps here if required
            # Example:
            # {
            #     'type': 'StringMatchValidation',
            #     'params': {'expected_string': 'некоторое_ожидаемое_слово'}
            # }
        ]

        generation_request = GenerationRequest(
            data_for_placeholders=data_for_placeholders,
            unformatted_prompt=unformatted_prompt,
            model="gpt-4o",  # Use the model specified in __init__
            pipeline_config=pipeline_config,
            operation_name="translate_to_russian",
            request_id=request_id
        )

        # Execute the generation synchronously
        generation_result = self.execute_generation(generation_request)
        return generation_result
    async def translate_to_russian_async(self, input_paragraph: str, request_id: Optional[Union[str, int]] = None) -> GenerationResult:
        # Concurrency control is handled in BaseLLMService
        data_for_placeholders = {'input_paragraph': input_paragraph}
        order = ["input_paragraph", "translate_to_russian"]

        unformatted_prompt = self.generation_engine.craft_prompt(data_for_placeholders, order)

        generation_request = GenerationRequest(
            data_for_placeholders=data_for_placeholders,
            unformatted_prompt=unformatted_prompt,
            model="gpt-3.5-turbo",
            output_type="str",
            use_string2dict=False,
            operation_name="translate_to_russian",
            request_id=request_id
        )

        # Execute the generation asynchronously
        generation_result = await self.execute_generation_async(generation_request)
        return generation_result
