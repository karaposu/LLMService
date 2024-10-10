# postprocessor.py

import json
import logging
from typing import Any, Optional, Dict
from string2dict import String2Dict  # Ensure this is installed or available

from .schemas import PostprocessingResult

class Postprocessor:
    def __init__(self, logger: Optional[logging.Logger] = None, debug: bool = False):
        self.logger = logger or logging.getLogger(__name__)
        self.debug = debug
        self.s2d = String2Dict()

    def postprocess(self, llm_output: Any, postprocess_config: Dict[str, Any]) -> PostprocessingResult:
        """
        Post-processes the LLM output based on the provided configuration.
        """
        result = PostprocessingResult(success=True, result=llm_output)

        if self.debug:
            self.logger.debug("Postprocessing...")

        # Initialize current_result with the raw LLM output
        current_result = llm_output

        # Step 1: Convert output to dict using s2d.run()
        if postprocess_config.get("postprocess_to_dict", False):
            current_result = self._postprocess_to_dict(current_result, result)

        # Step 2: Extract content with a key
        extract_key = postprocess_config.get("extract_content_with_a_key")
        if extract_key:
            current_result = self._extract_content_with_key(current_result, extract_key, result)

        # Step 3: String match validation
        if postprocess_config.get("string_match_validation", False):
            expected_string = postprocess_config.get("expected_string", "")
            self._string_match_validation(current_result, expected_string, result)

        # Step 4: JSON loading (if required)
        if postprocess_config.get("json_load", False):
            current_result = self._json_load(current_result, result)

        # Update the final result
        result.result = current_result

        return result

    def _postprocess_to_dict(self, input_data: Any, result: PostprocessingResult) -> Any:
        """Converts the input data to a dictionary using s2d.run()."""
        try:
            s2d_result = self.s2d.run(input_data)
            result.s2d_run_status = True
            result.s2d_run_result = s2d_result
            if self.debug:
                self.logger.debug(f"s2d.run() successful: {s2d_result}")
            return s2d_result
        except Exception as e:
            result.success = False
            result.error = f"s2d.run() failed: {e}"
            result.s2d_run_status = False
            if self.debug:
                self.logger.error(result.error)
            return input_data  # Return original data to continue processing

    def _extract_content_with_key(self, input_data: Any, extract_key: str, result: PostprocessingResult) -> Any:
        """Extracts content from the input data using the specified key."""
        if isinstance(input_data, dict):
            if extract_key in input_data:
                extracted_value = input_data[extract_key]
                result.extract_key_status = True
                result.extract_key_result = extracted_value
                if self.debug:
                    self.logger.debug(f"Extracted key '{extract_key}': {extracted_value}")
                return extracted_value
            else:
                result.success = False
                error_msg = f"Key '{extract_key}' not found in the result."
                result.error = error_msg
                result.extract_key_status = False
                if self.debug:
                    self.logger.error(error_msg)
                return input_data  # Return original data to continue processing
        else:
            result.success = False
            error_msg = "Current result is not a dictionary; cannot extract key."
            result.error = error_msg
            result.extract_key_status = False
            if self.debug:
                self.logger.error(error_msg)
            return input_data  # Return original data to continue processing

    def _string_match_validation(self, input_data: Any, expected_string: str, result: PostprocessingResult):
        """Validates that the expected string is present in the input data."""
        if expected_string in str(input_data):
            result.string_match_status = True
            result.string_match_result = True
            if self.debug:
                self.logger.debug(f"String match validation passed for '{expected_string}'.")
        else:
            result.success = False
            error_msg = f"Expected string '{expected_string}' not found in the result."
            result.error = error_msg
            result.string_match_status = False
            result.string_match_result = False
            if self.debug:
                self.logger.error(error_msg)

    def _json_load(self, input_data: Any, result: PostprocessingResult) -> Any:
        """Attempts to load the input data as JSON."""
        try:
            json_result = json.loads(input_data)
            result.json_load_status = True
            result.json_load_result = json_result
            if self.debug:
                self.logger.debug(f"JSON load successful: {json_result}")
            return json_result
        except json.JSONDecodeError as e:
            result.success = False
            error_msg = f"JSON loading failed: {e}"
            result.error = error_msg
            result.json_load_status = False
            if self.debug:
                self.logger.error(error_msg)
            return input_data  # Return original data to continue processing

def main():
    import logging

    # Set up basic logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('PostprocessorTest')

    # Create a Postprocessor instance
    postprocessor = Postprocessor(logger=logger, debug=True)

    # Sample LLM outputs
    llm_output_str = "The answer is 42."
    llm_output_dict_str = "{'answer': '42', 'explanation': 'The meaning of life.'}"
    llm_output_json_str = '{"answer": "42", "explanation": "The meaning of life."}'

    # Define postprocess_config for different tests
    # Test 1: Convert string representation of dict to actual dict using s2d.run()
    postprocess_config_1 = {
        "postprocess_to_dict": True,
    }

    # Test 2: Extract a key from the dict
    postprocess_config_2 = {
        "postprocess_to_dict": True,
        "extract_content_with_a_key": "answer",
    }

    # Test 3: String match validation
    postprocess_config_3 = {
        "string_match_validation": True,
        "expected_string": "42",
    }

    # Test 4: JSON load
    postprocess_config_4 = {
        "json_load": True,
    }

    # Test 5: Combination of steps
    postprocess_config_5 = {
        "postprocess_to_dict": True,
        "extract_content_with_a_key": "answer",
        "string_match_validation": True,
        "expected_string": "42",
    }

    # Run tests
    print("\nTest 1: Convert string representation of dict to actual dict")
    result1 = postprocessor.postprocess(llm_output_dict_str, postprocess_config_1)
    print("Result:", result1.result)
    print("Success:", result1.success)
    print("Error:", result1.error)

    print("\nTest 2: Extract 'answer' key from dict")
    result2 = postprocessor.postprocess(llm_output_dict_str, postprocess_config_2)
    print("Result:", result2.result)
    print("Success:", result2.success)
    print("Error:", result2.error)

    print("\nTest 3: String match validation")
    result3 = postprocessor.postprocess(llm_output_str, postprocess_config_3)
    print("Result:", result3.result)
    print("Success:", result3.success)
    print("Error:", result3.error)

    print("\nTest 4: JSON load")
    result4 = postprocessor.postprocess(llm_output_json_str, postprocess_config_4)
    print("Result:", result4.result)
    print("Success:", result4.success)
    print("Error:", result4.error)

    print("\nTest 5: Combination of steps")
    result5 = postprocessor.postprocess(llm_output_dict_str, postprocess_config_5)
    print("Result:", result5.result)
    print("Success:", result5.success)
    print("Error:", result5.error)

if __name__ == '__main__':
    main()
