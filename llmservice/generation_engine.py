# generation_engine.py

import logging
import time
from typing import Optional, Dict, Any

from llmservice.llm_handler import LLMHandler
from llmservice.postprocessor import Postprocessor
from llmservice.schemas import GenerationRequest, GenerationResult
from string2dict import String2Dict  # Ensure this is installed or available
from proteas import Proteas  # Ensure this is installed or available
from langchain_core.prompts import PromptTemplate
from langchain_core.prompts.string import get_template_variables


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Costs per model (example values, adjust as needed)
gpt_models_input_cost = {
    'gpt-4o': 5 / 1000000,
    "gpt-4o-2024-08-06": 2.5 / 1000000,
    'gpt-4o-mini': 0.15 / 1000000,
    'o1-preview': 15 / 1000000,
    'o1-mini': 3 / 1000000
}

gpt_models_output_cost = {
    'gpt-4o': 15 / 1000000,
    "gpt-4o-2024-08-06": 10 / 1000000,
    'gpt-4o-mini': 0.6 / 1000000,
    'o1-preview': 60 / 1000000,
    'o1-mini': 12 / 1000000
}


class GenerationEngine:
    def __init__(self, llm_handler=None, model_name=None, logger=None, debug=False):
        """
        Initializes the GenerationEngine.

        :param llm_handler: Optional LLMHandler instance.
        :param model_name: Default model name to use.
        :param logger: Optional logger instance.
        :param debug: Debug flag.
        """
        self.logger = logger or logging.getLogger(__name__)
        self.debug = debug
        self.s2d = String2Dict()

        if llm_handler:
            self.llm_handler = llm_handler
        else:
            self.llm_handler = LLMHandler(model_name=model_name, logger=self.logger)

        self.proteas = Proteas()

        self.postprocessor = Postprocessor(logger=self.logger, debug=self.debug)

        if self.debug:
            self.logger.setLevel(logging.DEBUG)

    def load_prompts(self, yaml_file_path):
        """Loads prompts from a YAML file using Proteas."""
        self.proteas.load_unit_skeletons_from_yaml(yaml_file_path)

    def craft_prompt(self, placeholder_dict: Dict[str, Any], order: Optional[list] = None) -> str:
        """
        Crafts the prompt using Proteas with the given placeholders and order.

        :param placeholder_dict: Dictionary of placeholder values.
        :param order: Optional list specifying the order of units.
        :return: Unformatted prompt string.
        """
        unformatted_prompt = self.proteas.craft(units=order, placeholder_dict=placeholder_dict)
        return unformatted_prompt

    def cost_calculator(self, input_token, output_token, model_name):
        if model_name not in gpt_models_input_cost or model_name not in gpt_models_output_cost:
            self.logger.error(f"Unsupported model name: {model_name}")
            raise ValueError(f"Unsupported model name: {model_name}")

        input_cost = gpt_models_input_cost[model_name] * int(input_token)
        output_cost = gpt_models_output_cost[model_name] * int(output_token)

        return input_cost, output_cost

    def generate_output(self, generation_request: GenerationRequest) -> GenerationResult:
        """
        Synchronously generates the output and processes postprocessing.

        :param generation_request: GenerationRequest object containing all necessary data.
        :return: GenerationResult object with the output and metadata.
        """
        # Unpack the GenerationRequest
        placeholders = generation_request.data_for_placeholders
        unformatted_prompt = generation_request.unformatted_prompt

        # Generate the output synchronously
        generation_result = self.generate(
            unformatted_template=unformatted_prompt,
            data_for_placeholders=placeholders,
            model_name=generation_request.model
        )

        # Assign request_id and operation_name
        generation_result.request_id = generation_request.request_id
        generation_result.operation_name = generation_request.operation_name

        # Postprocessing
        if generation_request.postprocess_config:
            postprocessing_result = self.postprocessor.postprocess(
                generation_result.content, generation_request.postprocess_config)
            generation_result.postprocessing_result = postprocessing_result
            if postprocessing_result.success:
                generation_result.content = postprocessing_result.result
            else:
                generation_result.success = False
                generation_result.error_message = postprocessing_result.error
        else:
            generation_result.postprocessing_result = None

        return generation_result

    async def generate_output_async(self, generation_request: GenerationRequest) -> GenerationResult:
        """
        Asynchronously generates the output and processes postprocessing.

        :param generation_request: GenerationRequest object containing all necessary data.
        :return: GenerationResult object with the output and metadata.
        """
        # Unpack the GenerationRequest
        placeholders = generation_request.data_for_placeholders
        unformatted_prompt = generation_request.unformatted_prompt

        # Generate the output asynchronously
        generation_result = await self.generate_async(
            unformatted_template=unformatted_prompt,
            data_for_placeholders=placeholders,
            model_name=generation_request.model
        )

        # Assign request_id and operation_name
        generation_result.request_id = generation_request.request_id
        generation_result.operation_name = generation_request.operation_name

        # Postprocessing
        if generation_request.postprocess_config:
            postprocessing_result = self.postprocessor.postprocess(
                generation_result.content, generation_request.postprocess_config)
            generation_result.postprocessing_result = postprocessing_result
            if postprocessing_result.success:
                generation_result.content = postprocessing_result.result
            else:
                generation_result.success = False
                generation_result.error_message = postprocessing_result.error
        else:
            generation_result.postprocessing_result = None

        return generation_result

    def generate(self, unformatted_template=None, data_for_placeholders=None, preprompts=None, debug=False, model_name=None):
        """
        Synchronously generates the content using the LLMHandler.

        :param unformatted_template: The unformatted prompt template.
        :param data_for_placeholders: Data to fill the placeholders.
        :param preprompts: Optional preprompts.
        :param debug: Debug flag.
        :param model_name: Model name to use.
        :return: GenerationResult object.
        """
        if preprompts:
            unformatted_prompt = self.proteas.craft(
                units=preprompts,
                placeholder_dict=data_for_placeholders,
            )
        else:
            unformatted_prompt = unformatted_template

        meta = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "elapsed_time_for_invoke": 0,
            "input_cost": 0,
            "output_cost": 0,
            "total_cost": 0,
        }

        t0 = time.time()

        # Validate placeholders
        existing_placeholders = get_template_variables(unformatted_prompt, "f-string")
        missing_placeholders = set(existing_placeholders) - set(data_for_placeholders.keys())

        if missing_placeholders:
            raise ValueError(f"Missing data for placeholders: {missing_placeholders}")

        # Format the prompt
        prompt_template = PromptTemplate.from_template(unformatted_prompt)
        formatted_prompt = prompt_template.format(**data_for_placeholders)

        t1 = time.time()

        # Initialize LLMHandler with the model_name
        llm_handler = LLMHandler(model_name=model_name or self.llm_handler.model_name, logger=self.logger)

        # Invoke the LLM synchronously
        r, success = llm_handler.invoke(prompt=formatted_prompt)

        if not success:
            return GenerationResult(
                success=False,
                meta=meta,
                content=None,
                elapsed_time=0,
                error_message="LLM invocation failed",
                model=llm_handler.model_name,
                formatted_prompt=formatted_prompt
            )

        t2 = time.time()
        elapsed_time_for_invoke = t2 - t1
        meta["elapsed_time_for_invoke"] = elapsed_time_for_invoke

        if llm_handler.OPENAI_MODEL:
            try:
                meta["input_tokens"] = r.usage_metadata["input_tokens"]
                meta["output_tokens"] = r.usage_metadata["output_tokens"]
                meta["total_tokens"] = r.usage_metadata["total_tokens"]
            except KeyError as e:
                return GenerationResult(
                    success=False,
                    meta=meta,
                    content=None,
                    elapsed_time=elapsed_time_for_invoke,
                    error_message="Token usage metadata missing",
                    model=llm_handler.model_name,
                    formatted_prompt=formatted_prompt
                )

            input_cost, output_cost = self.cost_calculator(
                meta["input_tokens"], meta["output_tokens"], llm_handler.model_name)
            meta["input_cost"] = input_cost
            meta["output_cost"] = output_cost
            meta["total_cost"] = input_cost + output_cost

        return GenerationResult(
            success=True,
            meta=meta,
            content=r.content,
            elapsed_time=elapsed_time_for_invoke,
            error_message=None,
            model=llm_handler.model_name,
            formatted_prompt=formatted_prompt
        )

    async def generate_async(self, unformatted_template=None, data_for_placeholders=None, preprompts=None, debug=False, model_name=None):
        """
        Asynchronously generates the content using the LLMHandler.

        :param unformatted_template: The unformatted prompt template.
        :param data_for_placeholders: Data to fill the placeholders.
        :param preprompts: Optional preprompts.
        :param debug: Debug flag.
        :param model_name: Model name to use.
        :return: GenerationResult object.
        """
        if preprompts:
            unformatted_prompt = self.proteas.craft(
                units=preprompts,
                placeholder_dict=data_for_placeholders,
            )
        else:
            unformatted_prompt = unformatted_template

        meta = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "elapsed_time_for_invoke": 0,
            "input_cost": 0,
            "output_cost": 0,
            "total_cost": 0,
        }

        t0 = time.time()

        # Validate placeholders
        existing_placeholders = get_template_variables(unformatted_prompt, "f-string")
        missing_placeholders = set(existing_placeholders) - set(data_for_placeholders.keys())

        if missing_placeholders:
            raise ValueError(f"Missing data for placeholders: {missing_placeholders}")

        # Format the prompt
        prompt_template = PromptTemplate.from_template(unformatted_prompt)
        formatted_prompt = prompt_template.format(**data_for_placeholders)

        t1 = time.time()

        # Initialize LLMHandler with the model_name
        llm_handler = LLMHandler(model_name=model_name or self.llm_handler.model_name, logger=self.logger)

        # Invoke the LLM asynchronously
        r, success = await llm_handler.invoke_async(prompt=formatted_prompt)

        if not success:
            return GenerationResult(
                success=False,
                meta=meta,
                content=None,
                elapsed_time=0,
                error_message="LLM invocation failed",
                model=llm_handler.model_name,
                formatted_prompt=formatted_prompt
            )

        t2 = time.time()
        elapsed_time_for_invoke = t2 - t1
        meta["elapsed_time_for_invoke"] = elapsed_time_for_invoke

        if llm_handler.OPENAI_MODEL:
            try:
                meta["input_tokens"] = r.usage_metadata["input_tokens"]
                meta["output_tokens"] = r.usage_metadata["output_tokens"]
                meta["total_tokens"] = r.usage_metadata["total_tokens"]
            except KeyError as e:
                return GenerationResult(
                    success=False,
                    meta=meta,
                    content=None,
                    elapsed_time=elapsed_time_for_invoke,
                    error_message="Token usage metadata missing",
                    model=llm_handler.model_name,
                    formatted_prompt=formatted_prompt
                )

            input_cost, output_cost = self.cost_calculator(
                meta["input_tokens"], meta["output_tokens"], llm_handler.model_name)
            meta["input_cost"] = input_cost
            meta["output_cost"] = output_cost
            meta["total_cost"] = input_cost + output_cost

        return GenerationResult(
            success=True,
            meta=meta,
            content=r.content,
            elapsed_time=elapsed_time_for_invoke,
            error_message=None,
            model=llm_handler.model_name,
            formatted_prompt=formatted_prompt
        )
