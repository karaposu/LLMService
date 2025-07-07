# generation_engine.py

# to run python -m llmservice.generation_engine

import logging
import time
import asyncio
from typing import Optional, Dict, Any, List, Union, Literal
from dataclasses import dataclass, field, asdict, fields
import uuid

from llmservice.llm_handler import LLMHandler
from string2dict import String2Dict
from langchain_core.prompts import PromptTemplate

from .schemas import GenerationRequest, GenerationResult, PipelineStepResult, BackoffStats, LLMCallRequest
from .schemas import EventTimestamps
from .utils import _now_dt

logger = logging.getLogger(__name__)


class GenerationEngine:
    def __init__(self, llm_handler=None, model_name=None, debug=False):
        self.logger = logging.getLogger(__name__)
        self.debug = debug
        self.s2d = String2Dict()

        if llm_handler:
            self.llm_handler = llm_handler
        else:
            self.llm_handler = LLMHandler(model_name=model_name, logger=self.logger)

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

    def _new_trace_id(self) -> str:
        return str(uuid.uuid4())
    
    def _debug(self, message):
        if self.debug:
            self.logger.debug(message)

    def format_template(self, template: str, **kwargs) -> str:
        """
        Format a template string with placeholders using LangChain's PromptTemplate.
        
        :param template: Template string with {placeholder} syntax
        :param kwargs: Values for the placeholders
        :return: Formatted string
        """
        prompt_template = PromptTemplate.from_template(template)
        return prompt_template.format(**kwargs)

    def _convert_to_llm_call_request(self, generation_request: GenerationRequest) -> LLMCallRequest:
        """Convert GenerationRequest to LLMCallRequest."""
        # Convert to dict and handle field name mapping  
        data = asdict(generation_request)
        
        # Handle the one field name difference
        if 'model' in data:
            data['model_name'] = data.pop('model')
        
        # Filter to only LLMCallRequest fields and create
        llm_fields = {f.name for f in fields(LLMCallRequest)}
        return LLMCallRequest(**{
            k: v for k, v in data.items() 
            if k in llm_fields
        })

    async def generate_output_async(self, generation_request: GenerationRequest) -> GenerationResult:
        """
        Asynchronously generates the output and processes postprocessing.

        :param generation_request: GenerationRequest object containing all necessary data.
        :return: GenerationResult object with the output and metadata.
        """
        # Record when this generation was requested (wall‐clock UTC)
        generation_requested_at = _now_dt()
        
        # Convert GenerationRequest to LLMCallRequest
        llm_call_request = self._convert_to_llm_call_request(generation_request)
        
        # Execute the LLM call asynchronously
        generation_result = await self._execute_llm_call_async(
            llm_call_request, 
            generation_request.request_id, 
            generation_request.operation_name
        )

        # Set the original request and timestamps
        generation_result.generation_request = generation_request
        
        # Ensure `timestamps` exists and fill in requested time
        if generation_result.timestamps is None:
            generation_result.timestamps = EventTimestamps()
        generation_result.timestamps.generation_requested_at = generation_requested_at

        if not generation_result.success:
            # Calculate elapsed time even for failures
            generation_completed_at = _now_dt()
            generation_result.timestamps.generation_completed_at = generation_completed_at
            generation_result.elapsed_time = (generation_completed_at - generation_requested_at).total_seconds()
            return generation_result
        
        # Run any post‐processing pipeline (if configured)
        if generation_request.pipeline_config:
            generation_result = await self.execute_pipeline_async(
                generation_result,
                generation_request.pipeline_config
            )
            # After pipeline finishes, record postprocessing completion time
            generation_result.timestamps.postprocessing_completed_at = _now_dt()
        else:
            # If no pipeline, just set content = raw_content
            generation_result.content = generation_result.raw_content

        # Finally, record when generation fully completed
        generation_completed_at = _now_dt()
        generation_result.timestamps.generation_completed_at = generation_completed_at
        
        # ← FIXED: Calculate total elapsed time from start to finish (including pipeline)
        generation_result.elapsed_time = (generation_completed_at - generation_requested_at).total_seconds()

        return generation_result
 
    def generate_output(self, generation_request: GenerationRequest) -> GenerationResult:
        """
        Synchronously generates the output and processes postprocessing.

        :param generation_request: GenerationRequest object containing all necessary data.
        :return: GenerationResult object with the output and metadata.
        """
        generation_requested_at = _now_dt()
        
        # Convert GenerationRequest to LLMCallRequest
        llm_call_request = self._convert_to_llm_call_request(generation_request)
        
        # Execute the LLM call synchronously
        generation_result = self._execute_llm_call(
            llm_call_request,
            generation_request.request_id,
            generation_request.operation_name
        )

        # Set the original request and timestamps
        generation_result.generation_request = generation_request
        
        if generation_result.timestamps is None:
            generation_result.timestamps = EventTimestamps()
        generation_result.timestamps.generation_requested_at = generation_requested_at

        if not generation_result.success:
            # Calculate elapsed time even for failures
            generation_completed_at = _now_dt()
            generation_result.timestamps.generation_completed_at = generation_completed_at
            generation_result.elapsed_time = (generation_completed_at - generation_requested_at).total_seconds()
            return generation_result

        # Process the output using the pipeline
        if generation_request.pipeline_config:
            generation_result = self.execute_pipeline(generation_result, generation_request.pipeline_config)
            generation_result.timestamps.postprocessing_completed_at = _now_dt()
        else:
            # No postprocessing; assign raw_content to content
            generation_result.content = generation_result.raw_content
        
        generation_completed_at = _now_dt()
        generation_result.timestamps.generation_completed_at = generation_completed_at
        
        # ← FIXED: Calculate total elapsed time from start to finish (including pipeline)
        generation_result.elapsed_time = (generation_completed_at - generation_requested_at).total_seconds()
        
        return generation_result

    def _execute_llm_call(self, llm_call_request: LLMCallRequest, request_id, operation_name) -> GenerationResult:
        """Execute synchronous LLM call and convert response to GenerationResult."""
        trace_id = self._new_trace_id()
        
        invoke_response_data = self.llm_handler.process_call_request(llm_call_request)
        
        return self._build_generation_result(
            invoke_response_data, trace_id, request_id, operation_name, llm_call_request
        )

    async def _execute_llm_call_async(self, llm_call_request: LLMCallRequest, request_id, operation_name) -> GenerationResult:
        """Execute asynchronous LLM call and convert response to GenerationResult."""
        trace_id = self._new_trace_id()
        
        invoke_response_data = await self.llm_handler.process_call_request_async(llm_call_request)
        
        return self._build_generation_result(
            invoke_response_data, trace_id, request_id, operation_name, llm_call_request
        )

    def _build_generation_result(self, invoke_response_data, trace_id, request_id, operation_name, llm_call_request) -> GenerationResult:
        """Build GenerationResult from InvokeResponseData."""
        response = invoke_response_data.response
        success = invoke_response_data.success
        attempts = invoke_response_data.attempts
        usage = invoke_response_data.usage
        error_type = invoke_response_data.error_type
        
        total_invoke_duration_ms = invoke_response_data.total_duration_ms
        total_backoff_ms = invoke_response_data.total_backoff_ms
        last_error_message = invoke_response_data.last_error_message
        retried = invoke_response_data.retried
        attempt_count = invoke_response_data.attempt_count

        actual_retry_loops = max(0, attempt_count - 1)
        backoff = BackoffStats(
            retry_loops=actual_retry_loops,
            retry_ms=total_backoff_ms
        )

        # Extract content from response
        raw_content = None
        if success and response:
            if hasattr(response, 'content'):
                raw_content = response.content
            elif isinstance(response, str):
                raw_content = response
            else:
                raw_content = str(response)

        # Determine response type based on output format
        response_type = "text"  # default
        if llm_call_request.output_data_format == "audio":
            response_type = "audio"
        elif llm_call_request.output_data_format == "both":
            response_type = "multimodal"

        return GenerationResult(
            success=success,
            trace_id=trace_id,
            usage=usage,
            raw_content=raw_content,
            raw_response=response,  # ← CRITICAL: Preserve the complete raw response for audio access
            content=None,  # Will be set later during pipeline processing
            retried=retried,
            attempt_count=attempt_count,
            total_invoke_duration_ms=total_invoke_duration_ms,
            elapsed_time=None,  # ← Will be calculated later from actual start/end timestamps
            backoff=backoff,
            error_message=last_error_message,
            model=llm_call_request.model_name or self.llm_handler.model_name,
            formatted_prompt=llm_call_request.user_prompt,  # For backward compatibility
            response_type=response_type,  # ← FIXED: Set response type based on output format
            request_id=request_id,
            operation_name=operation_name,
            timestamps=EventTimestamps(attempts=attempts)
        )

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

    async def execute_pipeline_async(self, generation_result: GenerationResult, pipeline_config: List[Dict[str, Any]]) -> GenerationResult:
        """
        Asynchronous version of execute_pipeline.
        Every step is awaited *if* an async implementation exists;
        otherwise we fall back to the synchronous one.

        The logic / error handling mirrors the sync function 1-for-1 so the
        calling code can rely on identical behaviour.
        """
        current_content = generation_result.raw_content

        for step_config in pipeline_config:
            step_type = step_config.get("type")
            params = step_config.get("params", {})
            async_name = f"process_{step_type.lower()}_async"
            sync_name = f"process_{step_type.lower()}"

            # Prefer an async implementation ↓
            processing_method = getattr(self, async_name, None)
            is_async = processing_method is not None and asyncio.iscoroutinefunction(processing_method)

            if not is_async:
                processing_method = getattr(self, sync_name, None)

            step_result = PipelineStepResult(
                step_type=step_type,
                success=False,
                content_before=current_content,
                content_after=None,
            )

            if processing_method is None:
                err_msg = f"Unknown processing step type: {step_type}"
                step_result.error_message = err_msg
                generation_result.success = False
                generation_result.error_message = err_msg
                generation_result.pipeline_steps_results.append(step_result)
                return generation_result

            try:
                # Await async, call sync
                if is_async:
                    content_after = await processing_method(current_content, **params)
                else:
                    content_after = processing_method(current_content, **params)

                step_result.success = True
                step_result.content_after = content_after
                current_content = content_after

            except Exception as exc:
                step_result.error_message = str(exc)
                generation_result.success = False
                generation_result.error_message = (
                    f"Processing step '{step_type}' failed: {exc}"
                )
                self.logger.error(generation_result.error_message)
                generation_result.pipeline_steps_results.append(step_result)
                return generation_result

            # Record successful step
            generation_result.pipeline_steps_results.append(step_result)

        # All steps succeeded → update final content
        generation_result.content = current_content
        return generation_result

    # ================================================================
    # Pipeline Processing Methods
    # ================================================================

    async def process_semanticisolation_async(self, content: str, *, semantic_element_for_extraction: str) -> str:
        """
        Asynchronous counterpart of `process_semanticisolation`.

        • Builds the same "isolate the semantic element" prompt  
        • Uses *one existing* `GenerationEngine` / `LLMHandler` instance  
        • Awaits `self.generate_output_async(…)` so the event-loop is never blocked

        Parameters
        ----------
        content : str
            The original LLM answer that contains extra information.
        semantic_element_for_extraction : str
            The specific piece of information we want to isolate (e.g. "pure category").

        Returns
        -------
        str
            The isolated semantic element (e.g. just `"Retail Purchases"`).

        Raises
        ------
        RuntimeError
            If the downstream LLM call fails or the expected key is not found.
        """
        # Format the template with the provided data
        formatted_prompt = self.format_template(
            self.semantic_isolation_prompt_template,
            answer_to_be_refined=content,
            semantic_element_for_extraction=semantic_element_for_extraction
        )

        # Create a new GenerationRequest for the refinement call
        refine_request = GenerationRequest(
            user_prompt=formatted_prompt,
            model=self.llm_handler.model_name  # Use current model
        )

        # Execute the refinement call
        refine_result = await self.generate_output_async(refine_request)

        # Error handling
        if not refine_result.success:
            raise RuntimeError(
                f"Semantic-isolation LLM call failed: {refine_result.error_message}"
            )

        # Parse the JSON-ish string
        try:
            isolated_answer = self.s2d.run(refine_result.raw_content)["answer"]
        except Exception as exc:
            raise RuntimeError(
                f"Could not parse isolation response: {refine_result.raw_content!r}"
            ) from exc

        return isolated_answer

    def process_semanticisolation(self, content: str, semantic_element_for_extraction: str) -> str:
        """
        Processes content using semantic isolation.

        :param content: The content to process.
        :param semantic_element_for_extraction: The semantic element to extract.
        :return: The isolated semantic element.
        """
        # Format the template with the provided data
        formatted_prompt = self.format_template(
            self.semantic_isolation_prompt_template,
            answer_to_be_refined=content,
            semantic_element_for_extraction=semantic_element_for_extraction
        )

        # Create a new GenerationRequest for the refinement call
        refine_request = GenerationRequest(
            user_prompt=formatted_prompt,
            model=self.llm_handler.model_name  # Use current model
        )

        # Execute the refinement call
        refine_result = self.generate_output(refine_request)

        if not refine_result.success:
            raise ValueError(f"Semantic isolation failed: {refine_result.error_message}")

        # Parse the LLM response to extract 'answer'
        s2d_result = self.s2d.run(refine_result.raw_content)
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


# Main function for testing
def main():
    import logging
    import sys
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

    generation_engine = GenerationEngine(model_name='gpt-4o-mini')

    # Test basic generation with new schema
    print("=== Testing Basic Generation ===")
    gen_request = GenerationRequest(
        user_prompt='What is the capital of France?',
        request_id=1,
        operation_name='test_capital'
    )

    generation_result = generation_engine.generate_output(gen_request)
    print(f"Success: {generation_result.success}")
    print(f"Content: {generation_result.content}")
    print(f"Model: {generation_result.model}")
    print(f"Usage: {generation_result.usage}")

    # Test semantic isolation pipeline
    print("\n=== Testing Semantic Isolation Pipeline ===")
    pipeline_request = GenerationRequest(
        user_prompt='The patient shows symptoms of severe headache and nausea. The diagnosis is migraine. Treatment includes rest and pain medication.',
        pipeline_config=[
            {
                'type': 'SemanticIsolation',
                'params': {
                    'semantic_element_for_extraction': 'symptoms only'
                }
            }
        ],
        request_id=2,
        operation_name='extract_symptoms'
    )

    pipeline_result = generation_engine.generate_output(pipeline_request)
    print(f"Success: {pipeline_result.success}")
    print(f"Raw Content: {pipeline_result.raw_content}")
    print(f"Final Content: {pipeline_result.content}")
    print(f"Pipeline Steps: {len(pipeline_result.pipeline_steps_results)}")
    
    if pipeline_result.pipeline_steps_results:
        for i, step in enumerate(pipeline_result.pipeline_steps_results):
            print(f"  Step {i+1}: {step.step_type} - {'✓' if step.success else '✗'}")
            if step.success:
                print(f"    Result: {step.content_after}")

    # Test multi-step pipeline
    print("\n=== Testing Multi-Step Pipeline ===")
    multi_pipeline_request = GenerationRequest(
        user_prompt='Return patient information in JSON format with fields: name, age, symptoms, diagnosis. Use this data: Patient John, 30 years old, has headache and fever, diagnosed with flu.',
        pipeline_config=[
            {
                'type': 'JSONLoad',
                'params': {}
            },
            {
                'type': 'ExtractValue',
                'params': {
                    'key': 'symptoms'
                }
            }
        ],
        request_id=3,
        operation_name='extract_json_symptoms'
    )

    multi_result = generation_engine.generate_output(multi_pipeline_request)
    print(f"Success: {multi_result.success}")
    print(f"Raw Content: {multi_result.raw_content}")
    print(f"Final Content: {multi_result.content}")
    print(f"Pipeline Steps: {len(multi_result.pipeline_steps_results)}")

    # Test audio input (multimodal)
    print("\n=== Testing Audio Input (Speech-to-Text) ===")
    try:
        import base64
        from pathlib import Path
        
        wav_path = Path("llmservice/my_voice.wav")
        if wav_path.exists():
            # Read and base64-encode the audio file
            b64_wav = base64.b64encode(wav_path.read_bytes()).decode("ascii")
            
            audio_input_request = GenerationRequest(
                model="gpt-4o-audio-preview",
                user_prompt="Please answer the question in the audio and explain your reasoning:",
                input_audio_b64=b64_wav,
                request_id=4,
                operation_name='process_audio_input'
            )
            
            audio_input_result = generation_engine.generate_output(audio_input_request)
            print(f"Audio Input Success: {audio_input_result.success}")
            if audio_input_result.success:
                print(f"Audio Input Response: {audio_input_result.content}")
                print(f"Audio Input Usage: {audio_input_result.usage}")
            else:
                print(f"Audio Input Error: {audio_input_result.error_message}")
        else:
            print(f"Audio file not found at {wav_path.resolve()}")
            print("To test audio input, place a WAV file at that location.")
    except Exception as e:
        print(f"Audio input test failed: {e}")

    # Test audio output (text-to-speech) - WITH SIMPLIFIED SAVING
    print("\n=== Testing Audio Output (Text-to-Speech) ===")
    try:
        audio_output_request = GenerationRequest(
            model="gpt-4o-audio-preview",
            user_prompt="Please say 'Hello, this is a test of audio output from the generation engine' in a friendly voice.",
            output_data_format="audio",
            audio_output_config={"voice": "alloy", "format": "wav"},
            request_id=5,
            operation_name='generate_audio_output'
        )
        
        audio_output_result = generation_engine.generate_output(audio_output_request)
        print(f"Audio Output Success: {audio_output_result.success}")
        
        if audio_output_result.success:
            print(f"Audio Output Usage: {audio_output_result.usage}")
            
            # Simple audio saving using convenience methods
            if audio_output_result.save_audio("llmservice/generation_engine_audio_output.wav"):
                audio_data = audio_output_result.get_audio_data()
                print(f"✅ Audio saved to: llmservice/generation_engine_audio_output.wav")
                print(f"Audio size: {len(audio_data)} bytes")
                
                transcript = audio_output_result.get_audio_transcript()
                if transcript:
                    print(f"Audio transcript: {transcript}")
            else:
                print("⚠️ Could not save audio file")
        else:
            print(f"Audio Output Error: {audio_output_result.error_message}")
            
    except Exception as e:
        print(f"Audio output test failed: {e}")

    # Test both text and audio output - SIMPLIFIED VERSION
    print("\n=== Testing Both Text + Audio Output ===")
    try:
        both_output_request = GenerationRequest(
            model="gpt-4o-audio-preview",
            user_prompt="Explain what machine learning is in simple terms, suitable for a 10-year-old.",
            output_data_format="both",
            audio_output_config={"voice": "shimmer", "format": "wav"},
            request_id=6,
            operation_name='generate_both_outputs'
        )
        
        both_result = generation_engine.generate_output(both_output_request)
        print(f"Both Output Success: {both_result.success}")
        
        if both_result.success:
            # Text output
            print(f"Text Response: {both_result.content[:100]}..." if both_result.content else "No text content")
            print(f"Both Output Usage: {both_result.usage}")
            
            # Audio output - now simple!
            audio_data = both_result.get_audio_data()
            if audio_data:
                # Save audio using the convenience method
                if both_result.save_audio("llmservice/generation_engine_both_output.wav"):
                    print(f"✅ Audio saved to: llmservice/generation_engine_both_output.wav")
                    print(f"Audio size: {len(audio_data)} bytes")
                else:
                    print("⚠️ Could not save audio file")
                
                # Get transcript if available
                transcript = both_result.get_audio_transcript()
                if transcript:
                    print(f"Audio transcript: {transcript}")
                
                print("✅ Both text and audio generation completed")
            else:
                print("⚠️ No audio data found in the response")
                print("✅ Text generation completed")
        else:
            print(f"Both Output Error: {both_result.error_message}")
            
    except Exception as e:
        print(f"Both output test failed: {e}")

    # Test audio input with pipeline processing
    print("\n=== Testing Audio Input + Pipeline Processing ===")
    try:
        if wav_path.exists():
            audio_pipeline_request = GenerationRequest(
                model="gpt-4o-audio-preview",
                user_prompt="Please answer the question in the audio. Provide your response in JSON format with fields: question, answer, confidence.",
                input_audio_b64=b64_wav,
                pipeline_config=[
                    {
                        'type': 'ConvertToDict',
                        'params': {}
                    },
                    {
                        'type': 'ExtractValue',
                        'params': {
                            'key': 'answer'
                        }
                    }
                ],
                request_id=7,
                operation_name='audio_with_pipeline'
            )
            
            audio_pipeline_result = generation_engine.generate_output(audio_pipeline_request)
            print(f"Audio + Pipeline Success: {audio_pipeline_result.success}")
            if audio_pipeline_result.success:
                print(f"Raw Audio Response: {audio_pipeline_result.raw_content}")
                print(f"Pipeline Processed Content: {audio_pipeline_result.content}")
                print(f"Pipeline Steps: {len(audio_pipeline_result.pipeline_steps_results)}")
                for i, step in enumerate(audio_pipeline_result.pipeline_steps_results):
                    print(f"  Step {i+1}: {step.step_type} - {'✓' if step.success else '✗'}")
            else:
                print(f"Audio + Pipeline Error: {audio_pipeline_result.error_message}")
        else:
            print("Skipping audio + pipeline test - no audio file available")
    except Exception as e:
        print(f"Audio + pipeline test failed: {e}")

    # Test access to raw response
    print("\n=== Testing Raw Response Access ===")
    try:
        test_request = GenerationRequest(
            model="gpt-4o-mini",
            user_prompt="What is 2+2?",
            request_id=8,
            operation_name='test_raw_response'
        )
        
        test_result = generation_engine.generate_output(test_request)
        print(f"Raw Response Access Success: {test_result.success}")
        
        if test_result.success:
            print(f"Raw response type: {type(test_result.raw_response)}")
            print(f"Raw response available: {test_result.raw_response is not None}")
            
            # You can now access any part of the raw response
            if test_result.raw_response:
                print(f"Raw response has content: {hasattr(test_result.raw_response, 'content')}")
                if hasattr(test_result.raw_response, 'usage_metadata'):
                    print(f"Raw response usage metadata: {test_result.raw_response.usage_metadata}")
                    
    except Exception as e:
        print(f"Raw response test failed: {e}")

    # Test audio-only output
    print("\n=== Testing Audio-Only Output ===")
    try:
        audio_only_request = GenerationRequest(
            model="gpt-4o-audio-preview",
            user_prompt="Please count from 1 to 5 slowly and clearly.",
            output_data_format="audio",
            audio_output_config={"voice": "echo", "format": "wav"},
            request_id=9,
            operation_name='generate_audio_only'
        )
        
        audio_only_result = generation_engine.generate_output(audio_only_request)
        print(f"Audio-Only Success: {audio_only_result.success}")
        
        if audio_only_result.success:
            print(f"Audio-Only Usage: {audio_only_result.usage}")
            
            # Save audio
            if audio_only_result.save_audio("llmservice/generation_engine_audio_only.wav"):
                audio_data = audio_only_result.get_audio_data()
                print(f"✅ Audio-only saved to: llmservice/generation_engine_audio_only.wav")
                print(f"Audio size: {len(audio_data)} bytes")
                
                transcript = audio_only_result.get_audio_transcript()
                if transcript:
                    print(f"Audio transcript: {transcript}")
            else:
                print("⚠️ Could not save audio-only file")
        else:
            print(f"Audio-Only Error: {audio_only_result.error_message}")
            
    except Exception as e:
        print(f"Audio-only test failed: {e}")


if __name__ == '__main__':
    main()