# # postprocessor.py
#
# import logging
# from typing import Any, Optional, Dict, List, Type
#
# from .schemas import PostprocessingResult, GenerationResult  # Ensure these are correctly imported
# from string2dict import String2Dict  # Import String2Dict
# import json
#
# # Base class for processing steps
# class ProcessingStep:
#     def __init__(self, params: Optional[Dict[str, Any]] = None):
#         self.params = params or {}
#
#     def process(self, data: Any) -> PostprocessingResult:
#         raise NotImplementedError("Each step must implement the process method.")
#
# # Define specific processing steps
# class SemanticIsolationStep(ProcessingStep):
#     def process(self, data: Any) -> PostprocessingResult:
#         try:
#             # Implement semantic isolation logic here
#             isolated_data = self.semantic_isolation(data)
#             return PostprocessingResult(success=True, result=isolated_data)
#         except Exception as e:
#             return PostprocessingResult(success=False, error=str(e))
#
#     def semantic_isolation(self, data):
#         # Placeholder for semantic isolation logic
#         # Replace with actual implementation
#         isolation_level = self.params.get('isolation_level', 1)
#         return f"Semantic Isolation Level {isolation_level}: {data}"
#
# class ConvertToDictStep(ProcessingStep):
#     def __init__(self, params: Optional[Dict[str, Any]] = None):
#         super().__init__(params)
#         self.s2d = String2Dict()
#
#     def process(self, data: Any) -> PostprocessingResult:
#         try:
#             # Implement conversion to dict logic here using s2d.run()
#             dict_data = self.convert_to_dict(data)
#             return PostprocessingResult(success=True, result=dict_data)
#         except Exception as e:
#             return PostprocessingResult(success=False, error=str(e))
#
#     def convert_to_dict(self, data):
#         # Use String2Dict to convert string to dict
#         return self.s2d.run(data)
#
# class ExtractValueStep(ProcessingStep):
#     def process(self, data: Any) -> PostprocessingResult:
#         try:
#             # Implement value extraction logic here
#             extracted_value = self.extract_value(data)
#             return PostprocessingResult(success=True, result=extracted_value)
#         except KeyError:
#             return PostprocessingResult(success=False, error=f"Key '{self.params.get('key')}' not found.")
#         except Exception as e:
#             return PostprocessingResult(success=False, error=str(e))
#
#     def extract_value(self, data: Dict[str, Any]):
#         # Extract value based on the provided key
#         key = self.params.get('key')
#         if not key:
#             raise ValueError("No key provided for extraction.")
#         return data[key]
#
# class StringMatchValidationStep(ProcessingStep):
#     def process(self, data: Any) -> PostprocessingResult:
#         expected_string = self.params.get('expected_string', '')
#         if expected_string in str(data):
#             return PostprocessingResult(success=True, result=data)
#         else:
#             error_msg = f"Expected string '{expected_string}' not found in the result."
#             return PostprocessingResult(success=False, error=error_msg)
#
# class JsonLoadStep(ProcessingStep):
#     def process(self, data: Any) -> PostprocessingResult:
#         try:
#             json_result = json.loads(data)
#             return PostprocessingResult(success=True, result=json_result)
#         except json.JSONDecodeError as e:
#             error_msg = f"JSON loading failed: {e}"
#             return PostprocessingResult(success=False, error=error_msg)
#
# # Mapping of step types to classes
# PROCESSING_STEP_CLASSES: Dict[str, Type[ProcessingStep]] = {
#     'SemanticIsolation': SemanticIsolationStep,
#     'ConvertToDict': ConvertToDictStep,
#     'ExtractValue': ExtractValueStep,
#     'StringMatchValidation': StringMatchValidationStep,
#     'JsonLoad': JsonLoadStep,
# }
#
# class PostprocessingPipeline:
#     def __init__(self, steps_config: Optional[List[Dict[str, Any]]] = None, logger: Optional[logging.Logger] = None):
#         self.logger = logger or logging.getLogger(__name__)
#         self.steps = self._initialize_steps(steps_config or [])
#
#     def _initialize_steps(self, steps_config: List[Dict[str, Any]]) -> List[ProcessingStep]:
#         steps = []
#         for step_config in steps_config:
#             step_type = step_config.get('type')
#             params = step_config.get('params', {})
#             step_class = PROCESSING_STEP_CLASSES.get(step_type)
#             if not step_class:
#                 self.logger.error(f"Unknown processing step type: {step_type}")
#                 continue
#             step = step_class(params)
#             steps.append(step)
#         return steps
#
#     def execute(self, data: Any) -> PostprocessingResult:
#         current_data = data
#         for step in self.steps:
#             result = step.process(current_data)
#             if not result.success:
#                 # Stop processing if a step fails
#                 if self.logger:
#                     self.logger.error(f"Processing step failed: {result.error}")
#                 return result
#             current_data = result.result
#         return PostprocessingResult(success=True, result=current_data)
#
# # Postprocessor class that utilizes the pipeline
# class Postprocessor:
#     def __init__(self, logger: Optional[logging.Logger] = None, debug: bool = False):
#         self.logger = logger or logging.getLogger(__name__)
#         self.debug = debug
#
#     def postprocess(self, generation_result: GenerationResult, postprocess_config: Dict[str, Any]) -> PostprocessingResult:
#         """
#         Post-processes the LLM output based on the provided configuration.
#         Updates the generation_result in place.
#         """
#         llm_output = generation_result.content
#
#         pipeline_config = postprocess_config.get('pipeline', [])
#         pipeline = PostprocessingPipeline(steps_config=pipeline_config, logger=self.logger)
#         result = pipeline.execute(llm_output)
#
#         if result.success:
#             generation_result.content = result.result
#         else:
#             generation_result.success = False
#             generation_result.error_message = result.error
#
#         # Attach the postprocessing result to generation_result
#         generation_result.postprocessing_result = result
#
#         if self.debug:
#             if result.success:
#                 self.logger.debug(f"Postprocessing successful: {result.result}")
#             else:
#                 self.logger.error(f"Postprocessing failed: {result.error}")
#
#         return result
#
# # Example usage
# if __name__ == '__main__':
#     import logging
#     from dataclasses import dataclass, field
#     from typing import Any, Dict, Optional, Union, Literal
#
#     # Define the necessary dataclasses if not imported
#     @dataclass
#     class PostprocessingResult:
#         success: bool
#         result: Optional[Any] = None
#         error: Optional[str] = None
#
#     @dataclass
#     class GenerationResult:
#         success: bool
#         meta: Dict[str, Any] = field(default_factory=dict)
#         content: Optional[str] = None
#         raw_content: Optional[str] = None
#         elapsed_time: Optional[int] = None
#         error_message: Optional[str] = None
#         model: Optional[str] = None
#         formatted_prompt: Optional[str] = None
#         unformatted_prompt: Optional[str] = None
#         operation_name: Optional[str] = None
#         request_id: Optional[Union[str, int]] = None
#         response_type: Optional[Literal["json", "str"]] = None
#         number_of_retries: Optional[int] = None
#         postprocessing_result: Optional[PostprocessingResult] = None
#
#     # Set up basic logging
#     logging.basicConfig(level=logging.DEBUG)
#     logger = logging.getLogger('PostprocessorTest')
#
#     # Sample LLM output that is not strictly valid JSON
#     llm_output_str = "The answer is 42."
#     llm_output_dict_str = "{'answer': '42', 'explanation': 'The meaning of life.'}"  # Note single quotes
#
#     # Define pipeline configuration
#     pipeline_config = {
#         'pipeline': [
#             {
#                 'type': 'ConvertToDict',
#             },
#             {
#                 'type': 'ExtractValue',
#                 'params': {'key': 'answer'}
#             },
#             {
#                 'type': 'StringMatchValidation',
#                 'params': {'expected_string': '42'}
#             }
#         ]
#     }
#
#     # Create a sample GenerationResult
#     generation_result = GenerationResult(
#         success=True,
#         content=llm_output_dict_str,
#         meta={},
#         model='gpt-3.5-turbo',
#         formatted_prompt='...',
#         request_id=1,
#         operation_name='test_operation'
#     )
#
#     # Create a Postprocessor instance
#     postprocessor = Postprocessor(logger=logger, debug=True)
#
#     # Run postprocessing
#     postprocess_config = pipeline_config  # In this case, they are the same
#     result = postprocessor.postprocess(generation_result, postprocess_config)
#
#     # Output the result
#     if generation_result.success:
#         print("Postprocessed Content:", generation_result.content)
#     else:
#         print("Error:", generation_result.error_message)
