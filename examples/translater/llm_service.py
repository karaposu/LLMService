# my_llm_service.py

import asyncio
from llmservice.base_service import BaseLLMService
from llmservice.generation_engine import GenerationRequest, GenerationResult
import logging
from typing import Optional, Union

class MyLLMService(BaseLLMService):
    def __init__(self, logger=None, max_concurrent_requests=5):
        super().__init__(logger=logger, model_name="gpt-4o", yaml_file_path='prompts.yaml')
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

    def translate_to_russian(self, input_paragraph: str, request_id: Optional[Union[str, int]] = None) -> GenerationResult:
        data_for_placeholders = {'input_paragraph': input_paragraph}
        order = ["input_paragraph", "translate_to_russian"]

        # Craft the unformatted prompt using the provided placeholders and order
        unformatted_prompt = self.generation_engine.craft_prompt(data_for_placeholders, order)

        # Create a GenerationRequest
        generation_request = GenerationRequest(
            data_for_placeholders=data_for_placeholders,
            unformatted_prompt=unformatted_prompt,
            model="gpt-3.5-turbo",  # Specify the model for this request
            output_type="str",
            use_string2dict=False,
            operation_name="translate_to_russian",
            request_id=request_id
        )

        # Execute the generation synchronously
        generation_result = self.execute_generation(generation_request)

        return generation_result

    async def translate_to_russian_async(self, input_paragraph: str, request_id: Optional[Union[str, int]] = None) -> GenerationResult:
        # Use a semaphore to limit the number of concurrent requests
        async with self.semaphore:
            data_for_placeholders = {'input_paragraph': input_paragraph}
            order = ["input_paragraph", "translate_to_russian"]

            # Craft the unformatted prompt using the provided placeholders and order
            unformatted_prompt = self.generation_engine.craft_prompt(data_for_placeholders, order)

            # Create a GenerationRequest
            generation_request = GenerationRequest(
                data_for_placeholders=data_for_placeholders,
                unformatted_prompt=unformatted_prompt,
                model="gpt-3.5-turbo",  # Specify the model for this request
                output_type="str",
                use_string2dict=False,
                operation_name="translate_to_russian",
                request_id=request_id
            )

            # Execute the generation asynchronously
            generation_result = await self.execute_generation_async(generation_request)

            return generation_result
