# generation_engine.py

import logging
import time
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field

from llmservice.llm_handler import LLMHandler  # Ensure this is correctly imported
from string2dict import String2Dict  # Ensure this is installed and available
from proteas import Proteas  # Ensure this is installed and available
from langchain_core.prompts import PromptTemplate
from langchain_core.prompts.string import get_template_variables

from .schemas import GenerationRequest, GenerationResult, PostprocessingResult , PipelineStepResult


logger = logging.getLogger(__name__)

# Costs per model (example values, adjust as needed)
gpt_models_input_cost = {'gpt-4o': 5 / 1000000,
                         "gpt-4o-2024-08-06": 2.5 / 1000000,
                         'gpt-4o-mini': 0.15 / 1000000,
                         'o1-preview': 15 / 1000000,
                         'o1-mini': 3 / 1000000}

gpt_models_output_cost = {'gpt-4o': 15 / 1000000,
                          "gpt-4o-2024-08-06":   10 / 1000000,
                          'gpt-4o-mini': 0.6 / 1000000,
                          'o1-preview': 60 / 1000000,
                          'o1-mini': 12 / 1000000}


class GenerationEngine:
    def __init__(self, llm_handler=None, model_name=None, debug=False):
        self.logger = logging.getLogger(__name__)
        self.debug = debug
        self.s2d = String2Dict()

        if llm_handler:
            self.llm_handler = llm_handler
        else:
            self.llm_handler = LLMHandler(model_name=model_name, logger=self.logger)

        self.proteas = Proteas()

        if self.debug:
            self.logger.setLevel(logging.DEBUG)

        # Define the semantic isolation prompt template
        self.semantic_isolation_prompt_template = """
Here is the text answer which includes the main desired information as well as some additional information: {answer_to_be_refined}
Here is the semantic element which should be used for extraction: {semantic_element_for_extraction}

From the given text answer, isolate and extract the semantic element.
Provide the answer strictly in the following JSON format, do not combine anything, remove all introductory or explanatory text that is not part of the semantic element:

'answer': 'here_is_isolated_answer'
"""

    def _debug(self, message):

        if self.debug:
            self.logger.debug(message)

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
            model_name=generation_request.model,
            request_id=generation_request.request_id,
            operation_name=generation_request.operation_name
        )

        if not generation_result.success:
            return generation_result

        # Process the output using the pipeline
        if generation_request.pipeline_config:
            generation_result = self.execute_pipeline(generation_result, generation_request.pipeline_config)
        else:
            # No postprocessing; assign raw_content to content
            generation_result.content = generation_result.raw_content

        return generation_result

    def execute_pipeline(self, generation_result: GenerationResult, pipeline_config: List[Dict[str, Any]]) -> GenerationResult:
        """
        Executes the processing pipeline on the generation result.

        :param generation_result: The initial GenerationResult from the LLM.
        :param pipeline_config: List of processing steps.
        :return: Updated GenerationResult after processing.
        """
        current_content = generation_result.raw_content
        for step_config in pipeline_config:
            step_type = step_config.get('type')
            params = step_config.get('params', {})
            method_name = f"process_{step_type.lower()}"
            processing_method = getattr(self, method_name, None)
            step_result = PipelineStepResult(
                step_type=step_type,
                success=False,
                content_before=current_content,
                content_after=None
            )
            if processing_method:
                try:
                    content_after = processing_method(current_content, **params)
                    step_result.success = True
                    step_result.content_after = content_after
                    current_content = content_after  # Update current_content for next step
                except Exception as e:
                    step_result.success = False
                    step_result.error_message = str(e)
                    generation_result.success = False
                    generation_result.error_message = f"Processing step '{step_type}' failed: {e}"
                    self.logger.error(generation_result.error_message)
                    # Record the failed step and exit the pipeline
                    generation_result.pipeline_steps_results.append(step_result)
                    return generation_result
            else:
                step_result.success = False
                error_msg = f"Unknown processing step type: {step_type}"
                step_result.error_message = error_msg
                generation_result.success = False
                generation_result.error_message = error_msg
                self.logger.error(generation_result.error_message)
                # Record the failed step and exit the pipeline
                generation_result.pipeline_steps_results.append(step_result)
                return generation_result
            # Record the successful step
            generation_result.pipeline_steps_results.append(step_result)

        # Update the final content
        generation_result.content = current_content
        return generation_result

    # Define processing methods
    def process_semanticisolation(self, content: str, semantic_element_for_extraction: str) -> str:
        """
        Processes content using semantic isolation.

        :param content: The content to process.
        :param semantic_element_for_extraction: The semantic element to extract.
        :return: The isolated semantic element.
        """
        answer_to_be_refined = content

        data_for_placeholders = {
            "answer_to_be_refined": answer_to_be_refined,
            "semantic_element_for_extraction": semantic_element_for_extraction,
        }
        unformatted_refiner_prompt = self.semantic_isolation_prompt_template

        refiner_result = self.generate(
            unformatted_template=unformatted_refiner_prompt,
            data_for_placeholders=data_for_placeholders
        )

        if not refiner_result.success:
            raise ValueError(f"Semantic isolation failed: {refiner_result.error_message}")

        # Parse the LLM response to extract 'answer'
        s2d_result = self.s2d.run(refiner_result.raw_content)
        isolated_answer = s2d_result.get('answer')
        if isolated_answer is None:
            raise ValueError("Isolated answer not found in the LLM response.")

        return isolated_answer

    def process_converttodict(self, content: Any) -> Dict[str, Any]:
        """
        Converts content to a dictionary.

        :param content: The content to convert.
        :return: The content as a dictionary.
        """
        if isinstance(content, dict):
            return content  # Already a dict
        return self.s2d.run(content)

    def process_extractvalue(self, content: Dict[str, Any], key: str) -> Any:
        """
        Extracts a value from a dictionary.

        :param content: The dictionary content.
        :param key: The key to extract.
        :return: The extracted value.
        """
        if key not in content:
            raise KeyError(f"Key '{key}' not found in content.")
        return content[key]

    def process_stringmatchvalidation(self, content: str, expected_string: str) -> str:
        """
        Validates that the expected string is present in the content.

        :param content: The content to validate.
        :param expected_string: The expected string to find.
        :return: The original content if validation passes.
        """
        if expected_string not in content:
            raise ValueError(f"Expected string '{expected_string}' not found in content.")
        return content

    def process_jsonload(self, content: str) -> Dict[str, Any]:
        """
        Loads content as JSON.

        :param content: The content to load.
        :return: The content as a JSON object.
        """
        import json
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON loading failed: {e}")

    # Implement the generate method
    def generate(self, unformatted_template, data_for_placeholders, model_name=None, request_id=None, operation_name=None) -> GenerationResult:
        """
        Generates content using the LLMHandler.

        :param unformatted_template: The unformatted prompt template.
        :param data_for_placeholders: Data to fill the placeholders.
        :param model_name: Model name to use.
        :param request_id: Optional request ID.
        :param operation_name: Optional operation name.
        :return: GenerationResult object.
        """
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
        existing_placeholders = get_template_variables(unformatted_template, "f-string")
        missing_placeholders = set(existing_placeholders) - set(data_for_placeholders.keys())

        if missing_placeholders:
            raise ValueError(f"Missing data for placeholders: {missing_placeholders}")

        # Format the prompt
        prompt_template = PromptTemplate.from_template(unformatted_template)
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
                raw_content=None,
                content=None,
                elapsed_time=0,
                error_message="LLM invocation failed",
                model=llm_handler.model_name,
                formatted_prompt=formatted_prompt,
                request_id=request_id,
                operation_name=operation_name
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
                    raw_content=None,
                    content=None,
                    elapsed_time=elapsed_time_for_invoke,
                    error_message="Token usage metadata missing",
                    model=llm_handler.model_name,
                    formatted_prompt=formatted_prompt,
                    unformatted_prompt=unformatted_template,
                    request_id=request_id,
                    operation_name=operation_name
                )

            input_cost, output_cost = self.cost_calculator(
                meta["input_tokens"], meta["output_tokens"], llm_handler.model_name)
            meta["input_cost"] = input_cost
            meta["output_cost"] = output_cost
            meta["total_cost"] = input_cost + output_cost

        return GenerationResult(
            success=True,
            meta=meta,
            raw_content=r.content,  # Assign initial LLM output
            content=None,           # Will be assigned after postprocessing
            elapsed_time=elapsed_time_for_invoke,
            error_message=None,
            model=llm_handler.model_name,
            formatted_prompt=formatted_prompt,
            unformatted_prompt=unformatted_template,
            request_id=request_id,
            operation_name=operation_name
        )

# Main function for testing
def main():
    import logging

    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )


    generation_engine = GenerationEngine(model_name='gpt-4o')

    placeholders = {'input_text': 'Patient shows symptoms of severe headache and nausea.'}
    unformatted_prompt = 'Provide a summary of the following clinical note: {input_text}'

    pipeline_config = [
        {
            'type': 'SemanticIsolation',
            'params': {
                'semantic_element_for_extraction': 'symptoms'
            }
        },
        # You can add more steps here if needed
    ]

    gen_request = GenerationRequest(
        data_for_placeholders=placeholders,
        unformatted_prompt=unformatted_prompt,
        model='gpt-4o',
        pipeline_config=pipeline_config,
        request_id=3,
        operation_name='extract_symptoms'
    )

    generation_result = generation_engine.generate_output(gen_request)

    if generation_result.success:
        logger.info("Final Result:")
        logger.info(generation_result.content)
        logger.info("Raw LLM Output:")
        logger.info(generation_result.raw_content)
    else:
        logger.info("Error:")
        logger.info(generation_result.error_message)

    logger.info("Pipeline Steps Results")
    for step_result in generation_result.pipeline_steps_results:
        logger.info(f"Step {step_result.step_type}")
        logger.info(f"Success {step_result.success}")

        if step_result.success:
            logger.info(f"Content Before: {step_result.content_before}")
            logger.info(f"Content After: {step_result.content_after}")
        else:
            logger.info(f"Error: {step_result.error_message}")

if __name__ == '__main__':
    main()
