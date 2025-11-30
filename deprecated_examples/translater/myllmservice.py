# myllmservice.py

import asyncio
from llmservice import BaseLLMService, GenerationRequest, GenerationResult
from typing import Optional, Union


class MyLLMService(BaseLLMService):
    def __init__(self):
        super().__init__(default_model_name="gpt-4o-mini")
        # now override defaults without modifying super()
        self.set_rate_limits(max_rpm=120, max_tpm=10_000)
        self.set_concurrency(10)

    # No need for a semaphore here, it's handled in BaseLLMService

    def translate_to_latin(self, input_paragraph: str) -> GenerationResult:
        my_prompt=f"translate this text to latin {input_paragraph}"

        generation_request = GenerationRequest(
            formatted_prompt=my_prompt,
            model="gpt-4o",  # Use the model specified in __init__
        )

        # Execute the generation synchronously
        generation_result = self.execute_generation(generation_request)
        return generation_result
    
    
    async def translate_to_latin_async(self, input_paragraph: str, request_id: Optional[Union[str, int]] = None) -> GenerationResult:
      
        my_prompt=f"translate this to to latin {input_paragraph}"

        generation_request = GenerationRequest(
            formatted_prompt=my_prompt,
            model="gpt-4o-mini",
            operation_name="translate_to_latin",
        )

        generation_result = await self.execute_generation_async(generation_request)
        return generation_result
