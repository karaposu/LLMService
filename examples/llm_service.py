from llmkit.base_service import BaseLLMService
from llmkit.generation_engine import GenerationEngine, GenerationRequest
import logging

class MyLLMService(BaseLLMService):
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.generation_engine = GenerationEngine(logger=self.logger, model_name="gpt-4")
        self.generation_engine.load_prompts('prompts.yaml')

    def translate_to_russian(self, input_paragraph: str):
        data_for_placeholders = {'input_paragraph': input_paragraph}
        order = ["input_paragraph", "translate_to_russian"]

        unformatted_prompt = self.generation_engine.craft_prompt(data_for_placeholders, order)

        generation_request = GenerationRequest(
            data_for_placeholders=data_for_placeholders,
            unformatted_prompt=unformatted_prompt,
            output_type="str",
            use_string2dict=False,
            operation_name="translate_to_russian"
        )

        generation_result = self.generation_engine.generate_output(generation_request)

        return generation_result.content











# #here is llm_service.py
#
# from typing import Optional, Dict, Any
# import logging
# from datetime import datetime
# import os
# from generation_engine import GenerationEngine
# from usage_stats import UsageStats
#
#
# def indent_log_pretty(logger_object, dictonary, lvl):
#     for key, value in dictonary.items():
#         logger_object.debug(f"{key}: %s", {value}, lvl=lvl)
#
#
# class LLMService:
#     def __init__(self, logger=None, allowed_models: Optional[list] = None):
#         self.logger = logger
#         # self.allowed_models = allowed_models or ['gpt-4o-2024-08-06']
#         self.allowed_models = allowed_models or ['gpt-4o-mini']
#         self.usage_stats = UsageStats()
#
#         self.gm = GenerationEngine(logger=self.logger,model_name=self.allowed_models[0])
#
#     def reset_usage(self):
#         self.usage_stats = UsageStats()
#
#     def translate_to_russian(self, input_paragraph):
#
#         data_for_placeholders = {
#             'input_paragraph': input_paragraph,
#         }
#         order = ["input_paragraph", "translate_to_russian"]
#
#         unformatted_prompt = self.gm.craft_prompt(data_for_placeholders, order)
#
#         generation_result = self.gm.generate_output(unformatted_prompt, data_for_placeholders)
#
#         return generation_result
#
#
#
#
