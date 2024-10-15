# my_llm_service.py

import asyncio
from llmservice.base_service import BaseLLMService
from llmservice.schemas import GenerationRequest, GenerationResult
from typing import Optional, Union
import os


class MyLLMService(BaseLLMService):
    def __init__(self, logger=None, max_concurrent_requests=5):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Construct the absolute path to prompts.yaml
        yaml_file_path = os.path.join(current_dir, 'prompts.yaml')

        super().__init__(
            logger=logger,
            model_name="gpt-4o",
            yaml_file_path=yaml_file_path,
            max_rpm=60,
            max_concurrent_requests=max_concurrent_requests,
        )


    def create_sql_code(self,
                        user_question: str,
                        database_desc,
                        request_id: Optional[Union[str, int]] = None) -> GenerationResult:


        data_for_placeholders = {"user_nlp_query": user_question,
                                 "my_database_schema": database_desc}

        print("-----------")

        print(data_for_placeholders)

        print( "-----------")

        order = ["my_database_schema", "user_nlp_query", "generate_sql_code"]

        # Craft the prompt using the generation engine
        unformatted_prompt = self.generation_engine.craft_prompt(data_for_placeholders, order)

        # Define any postprocessing steps if needed
        pipeline_config = [
            {
                'type': 'SemanticIsolation',
                'params': {
                    'semantic_element_for_extraction': 'SQL code'
                }
            }
            # {
            #     'type': 'ConvertToDict',
            #     'params': {}
            # },
            # {
            #     'type': 'ExtractValue',
            #     'params': {'key': 'answer'}  # Extract the 'answer' key from the dictionary
            # }
        ]
        generation_request = GenerationRequest(
            data_for_placeholders=data_for_placeholders,
            unformatted_prompt=unformatted_prompt,
            model="gpt-4o",  # Use the model specified in __init__
            pipeline_config=pipeline_config,
            operation_name="generate_sql_code",
            request_id=request_id
        )

        # Execute the generation synchronously
        generation_result = self.execute_generation(generation_request)
        return generation_result



