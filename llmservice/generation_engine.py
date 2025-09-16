# generation_engine.py

# to run python -m llmservice.generation_engine

import logging
import time
import asyncio
from typing import Optional, Dict, Any, List, Union, Literal
from dataclasses import dataclass, field, asdict, fields
import uuid

from llmservice.llm_handler import LLMHandler
from langchain_core.prompts import PromptTemplate

from .schemas import GenerationRequest, GenerationResult, BackoffStats, LLMCallRequest
from .schemas import EventTimestamps
from .utils import _now_dt

logger = logging.getLogger(__name__)


class GenerationEngine:
    def __init__(self, llm_handler=None, model_name=None, debug=False):
        self.logger = logging.getLogger(__name__)
        self.debug = debug

        if llm_handler:
            self.llm_handler = llm_handler
        else:
            self.llm_handler = LLMHandler(model_name=model_name, logger=self.logger)

        if self.debug:
            self.logger.setLevel(logging.DEBUG)

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
        Asynchronously generates the output with structured outputs support.

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
        
        # Set content = raw_content (no pipeline processing)
        generation_result.content = generation_result.raw_content

        # Finally, record when generation fully completed
        generation_completed_at = _now_dt()
        generation_result.timestamps.generation_completed_at = generation_completed_at
        
        # Calculate total elapsed time from start to finish
        generation_result.elapsed_time = (generation_completed_at - generation_requested_at).total_seconds()

        return generation_result
 
    def generate_output(self, generation_request: GenerationRequest) -> GenerationResult:
        """
        Synchronously generates the output with support for structured outputs.
        
        Uses response_schema for structured output when provided.
        Otherwise generates standard text.

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

        # Set the original request
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
        
        # Set content = raw_content (no pipeline processing)
        generation_result.content = generation_result.raw_content

        # Finally, record when generation fully completed
        generation_completed_at = _now_dt()
        generation_result.timestamps.generation_completed_at = generation_completed_at
        
        # Calculate total elapsed time from start to finish
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
            # Handle Responses API Response object
            if hasattr(response, 'output') and response.output:
                # Find the first message output (skip reasoning items)
                for output_item in response.output:
                    # Skip ResponseReasoningItem, look for ResponseOutputMessage
                    if hasattr(output_item, 'content') and output_item.content:
                        for content_item in output_item.content:
                            if hasattr(content_item, 'text'):
                                raw_content = content_item.text
                                break
                    if raw_content:
                        break
                # If still no content, check if it's a simple text response
                if not raw_content:
                    if hasattr(response, 'content'):
                        raw_content = response.content
                    elif isinstance(response, str):
                        raw_content = response
                    else:
                        raw_content = str(response)
            else:
                # Handle simple response types
                if hasattr(response, 'content'):
                    raw_content = response.content
                elif isinstance(response, str):
                    raw_content = response
                else:
                    raw_content = str(response)

        # Determine response type based on output format
        response_type = "text"  # default
        if llm_call_request.output_type == "json" or hasattr(llm_call_request, 'response_schema') and llm_call_request.response_schema:
            response_type = "json"
        elif llm_call_request.output_data_format == "audio":
            response_type = "audio"
        elif llm_call_request.output_data_format == "both":
            response_type = "multimodal"

        # Extract response_id from usage if available (Responses API)
        response_id = usage.get('response_id') if usage else None
        
        # For JSON responses, set content to raw_content
        content = raw_content if response_type == "json" else None
        
        return GenerationResult(
            success=success,
            trace_id=trace_id,
            usage=usage,
            raw_content=raw_content,
            raw_response=response,  # Preserve the complete raw response for audio access
            content=content,  # Set for JSON responses
            retried=retried,
            attempt_count=attempt_count,
            total_invoke_duration_ms=total_invoke_duration_ms,
            elapsed_time=None,  # Will be calculated later from actual start/end timestamps
            backoff=backoff,
            error_message=last_error_message,
            model=llm_call_request.model_name or self.llm_handler.model_name,
            formatted_prompt=llm_call_request.user_prompt,  # For backward compatibility
            response_type=response_type,  # Set response type based on output format
            response_id=response_id,  # Track response_id for CoT chaining
            request_id=request_id,
            operation_name=operation_name,
            timestamps=EventTimestamps(attempts=attempts)
        )

    # ============================================================================
    # Structured Output Support
    # ============================================================================
    
    def process_with_schema(self, 
                           content: str, 
                           schema: type,
                           instructions: str = None,
                           **kwargs) -> Any:
        """
        Process content with guaranteed structured output using Pydantic schema.
        
        :param content: The content to process
        :param schema: Pydantic model class defining the expected structure
        :param instructions: Optional system instructions
        :param kwargs: Additional parameters for generation request
        :return: Parsed Pydantic model instance
        """
        from pydantic import BaseModel
        import json
        
        # Validate schema is a Pydantic model
        if not issubclass(schema, BaseModel):
            raise ValueError(f"Schema must be a Pydantic BaseModel, got {type(schema)}")
        
        # Create generation request with schema
        request = GenerationRequest(
            user_prompt=content,
            system_prompt=instructions or f"Extract data according to the {schema.__name__} schema",
            response_schema=schema,
            reasoning_effort=kwargs.get('reasoning_effort', 'low'),  # Low reasoning for format compliance
            verbosity=kwargs.get('verbosity', None),  # Let model use default
            model=kwargs.get('model'),
            **{k: v for k, v in kwargs.items() if k not in ['reasoning_effort', 'verbosity', 'model']}
        )
        
        # Execute generation
        result = self.generate_output(request)
        
        if result.success:
            # Parse JSON response to Pydantic model
            if result.response_type == "json" and result.content:
                try:
                    # Content should already be valid JSON if structured output worked
                    if isinstance(result.content, str):
                        data = json.loads(result.content)
                    else:
                        data = result.content
                    
                    # Create and return Pydantic model instance
                    return schema(**data)
                except (json.JSONDecodeError, ValueError) as e:
                    raise ValueError(f"Failed to parse structured output: {e}")
            else:
                raise ValueError(f"Unexpected response type: {result.response_type}")
        else:
            raise ValueError(f"Generation failed: {result.error_message}")
    
    def generate_structured(self, 
                           prompt: str,
                           schema: type,
                           system: str = None,
                           **kwargs) -> Any:
        """
        Simplified interface for structured generation.
        
        :param prompt: User prompt
        :param schema: Pydantic model for the response structure
        :param system: Optional system prompt
        :param kwargs: Additional generation parameters
        :return: Parsed Pydantic model instance
        """
        return self.process_with_schema(
            content=prompt,
            schema=schema,
            instructions=system,
            **kwargs
        )
    
    def semantic_isolation_v2(self, content: str, element: str) -> str:
        """
        Semantic isolation using structured output - no parsing errors!
        
        :param content: Text to extract from
        :param element: Semantic element to isolate
        :return: Isolated text element
        """
        from llmservice.structured_schemas import SemanticIsolation
        
        result = self.process_with_schema(
            content=content,
            schema=SemanticIsolation,
            instructions=f"Extract only the following semantic element: {element}"
        )
        
        return result.answer
    
    def extract_entities(self, text: str) -> List[Dict]:
        """
        Extract structured entities from unstructured text.
        
        :param text: Text to extract entities from
        :return: List of extracted entities as dictionaries
        """
        from llmservice.structured_schemas import EntitiesList
        
        result = self.process_with_schema(
            content=text,
            schema=EntitiesList,
            instructions="Extract all named entities from the text"
        )
        
        return [e.model_dump() for e in result.entities]

    def generate_with_cot_chain(self, generation_request: GenerationRequest, 
                                previous_response_id: Optional[str] = None) -> GenerationResult:
        """
        Generate output with CoT chaining support for Responses API.
        
        :param generation_request: The generation request
        :param previous_response_id: Optional response_id from previous call to chain CoT
        :return: GenerationResult with response_id for future chaining
        """
        # Set the previous_response_id if provided
        if previous_response_id:
            generation_request.previous_response_id = previous_response_id
            self.logger.info(f"Chaining CoT with previous response: {previous_response_id}")
        
        # Execute the generation
        result = self.generate_output(generation_request)
        
        # Log the new response_id for potential future chaining
        if result.response_id:
            self.logger.info(f"Generated response with ID: {result.response_id} (can be used for chaining)")
        
        return result


# Optional: Main for testing
if __name__ == "__main__":
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    # Example with structured output
    from pydantic import BaseModel, Field
    from typing import List
    
    class SimpleExtraction(BaseModel):
        items: List[str] = Field(description="Extracted items")
        count: int = Field(description="Number of items")
    
    result = engine.generate_structured(
        prompt="List three colors",
        schema=SimpleExtraction,
        system="Extract the colors mentioned"
    )
    
    print(f"Extracted {result.count} items: {', '.join(result.items)}")