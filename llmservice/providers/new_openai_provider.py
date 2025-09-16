# llmservice/providers/new_openai_provider.py
"""
OpenAI Responses API provider implementation.
Uses the new Responses API instead of Chat Completions.
"""

import os
import logging
from typing import Any, Dict, List, Optional, Tuple, Type
from openai import OpenAI, AsyncOpenAI
from openai import RateLimitError, PermissionDeniedError

from .base import BaseLLMProvider
from ..schemas import LLMCallRequest, ErrorType


class ResponsesAPIProvider(BaseLLMProvider):
    """OpenAI Responses API provider with CoT support and native tools."""
    
    # Updated costs for all models (reasoning tokens separate)
    MODEL_COSTS = {
        # Current GPT-4 models (working with Responses API)
        'gpt-4o': {
            'input_token_cost': 2.5e-6,  # $2.50 per 1M tokens
            'output_token_cost': 10e-6,  # $10 per 1M tokens
            'reasoning_token_cost': 0  # No reasoning for standard models
        },
        'gpt-4o-mini': {
            'input_token_cost': 0.15e-6,  # $0.15 per 1M tokens
            'output_token_cost': 0.6e-6,  # $0.60 per 1M tokens
            'reasoning_token_cost': 0
        },
        'gpt-4o-audio-preview': {
            'input_token_cost': 2.5e-6,
            'output_token_cost': 10e-6,
            'reasoning_token_cost': 0
        },
        # GPT-5 series (from docs)
        'gpt-5': {
            'input_token_cost': 30e-6,  # $30 per 1M tokens
            'output_token_cost': 60e-6,  # $60 per 1M tokens
            'reasoning_token_cost': 45e-6  # Estimate between input/output
        },
        'gpt-5-mini': {
            'input_token_cost': 3e-6,
            'output_token_cost': 12e-6,
            'reasoning_token_cost': 7.5e-6
        },
        'gpt-5-nano': {
            'input_token_cost': 0.3e-6,
            'output_token_cost': 1.2e-6,
            'reasoning_token_cost': 0.75e-6
        },
        # GPT-4.1 models
        'gpt-4.1': {
            'input_token_cost': 2e-6,
            'output_token_cost': 8e-6,
            'reasoning_token_cost': 0  # No reasoning for non-reasoning models
        },
        'gpt-4.1-mini': {
            'input_token_cost': 0.4e-6,
            'output_token_cost': 1.6e-6,
            'reasoning_token_cost': 0
        },
        # O-series reasoning models
        'o1': {
            'input_token_cost': 15e-6,  # $15 per 1M tokens
            'output_token_cost': 60e-6,  # $60 per 1M tokens
            'reasoning_token_cost': 15e-6  # Reasoning tokens same as input
        },
        'o1-mini': {
            'input_token_cost': 3e-6,
            'output_token_cost': 12e-6,
            'reasoning_token_cost': 3e-6
        },
        'o1-preview': {
            'input_token_cost': 15e-6,
            'output_token_cost': 60e-6,
            'reasoning_token_cost': 15e-6
        },
        'o3': {
            'input_token_cost': 10e-6,
            'output_token_cost': 40e-6,
            'reasoning_token_cost': 10e-6
        },
        'o3-mini': {
            'input_token_cost': 2e-6,
            'output_token_cost': 8e-6,
            'reasoning_token_cost': 2e-6
        },
    }
    
    # Native tools available in Responses API
    NATIVE_TOOLS = {
        'web_search', 'file_search', 'code_interpreter', 
        'computer_use', 'image_generation', 'mcp'
    }
    
    def __init__(self, model_name: str, logger: Optional[logging.Logger] = None):
        super().__init__(model_name, logger)
        self.client = self._initialize_client()
        self.async_client = self._initialize_async_client()
        self.is_reasoning_model = model_name.startswith(('gpt-5', 'o'))
    
    @classmethod
    def supports_model(cls, model_name: str) -> bool:
        """Check if this provider supports the given model."""
        # Support all GPT-5 models and known GPT-4.1 models
        return (
            model_name in cls.MODEL_COSTS or
            model_name.startswith('gpt-5') or
            model_name.startswith('gpt-4.1')
        )
    
    def _initialize_client(self) -> OpenAI:
        """Initialize the OpenAI client for Responses API."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        return OpenAI(api_key=api_key)
    
    def _initialize_async_client(self) -> AsyncOpenAI:
        """Initialize the async OpenAI client for Responses API."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        return AsyncOpenAI(api_key=api_key)
    
    def convert_request(self, request: LLMCallRequest) -> Dict[str, Any]:
        """Convert LLMCallRequest to Responses API format."""
        
        # Build the input - can be string or messages array
        input_content = self._build_input(request)
        
        # Base payload for Responses API
        payload = {
            "model": request.model_name or self.model_name,
            "input": input_content,
        }
        
        # Add instructions if we have system prompt
        if request.system_prompt:
            payload["instructions"] = request.system_prompt
        
        # Add reasoning control for GPT-5 models
        if self.is_reasoning_model:
            # Default to medium if not specified
            reasoning_effort = "medium"
            if hasattr(request, 'reasoning_effort'):
                reasoning_effort = request.reasoning_effort
            payload["reasoning"] = {"effort": reasoning_effort}
        
        # Add verbosity control
        if hasattr(request, 'verbosity'):
            payload["text"] = {"verbosity": request.verbosity}
        
        # Add previous response ID for CoT chaining
        if hasattr(request, 'previous_response_id') and request.previous_response_id:
            payload["previous_response_id"] = request.previous_response_id
        
        # Add store parameter (default true for stateful context)
        if hasattr(request, 'store'):
            payload["store"] = request.store
        else:
            payload["store"] = True  # Default to stateful
        
        # Handle tools
        if request.tool_call:
            payload["tools"] = self._convert_tools(request.tool_call)
        
        # Handle structured output format
        if hasattr(request, 'response_schema') and request.response_schema:
            # Structured Output with Pydantic schema
            if "text" not in payload:
                payload["text"] = {}
            payload["text"]["format"] = self._build_json_schema(request.response_schema, 
                                                               getattr(request, 'strict_mode', True))
        elif hasattr(request, 'output_format') and request.output_format:
            # Legacy format specification
            if "text" not in payload:
                payload["text"] = {}
            payload["text"]["format"] = request.output_format
        elif request.output_type == "json":
            # Fallback to JSON mode for backward compatibility
            if "text" not in payload:
                payload["text"] = {}
            payload["text"]["format"] = {"type": "json_object"}
        
        # Note: Responses API handles audio differently than Chat Completions
        # Audio output is not configured via a separate parameter
        # TODO: Implement audio output when Responses API documentation is clearer
        
        return payload
    
    def _build_input(self, request: LLMCallRequest) -> Any:
        """Build input for Responses API - can be string or messages array."""
        
        # Simple case: just text
        if request.user_prompt and not (request.images or request.input_audio_b64):
            # For simple text, we can use string directly
            if request.assistant_text:
                # If there's assistant text, we need messages format
                messages = []
                messages.append({"role": "user", "content": request.user_prompt})
                messages.append({"role": "assistant", "content": request.assistant_text})
                return messages
            else:
                return request.user_prompt  # Simple string
        
        # Complex case: multimodal or multiple messages
        messages = []
        
        # Build user message with multimodal content
        if request.user_prompt or request.images or request.input_audio_b64:
            content = []
            
            # Add text (use input_text for Responses API)
            if request.user_prompt:
                content.append({"type": "input_text", "text": request.user_prompt})
            
            # Add images (use input_image for Responses API)
            if request.images:
                for img_b64 in request.images:
                    content.append({
                        "type": "input_image",
                        "image": {"data": img_b64}
                    })
            
            # Add audio (use input_audio for Responses API)
            if request.input_audio_b64:
                content.append({
                    "type": "input_audio",
                    "audio": {
                        "data": request.input_audio_b64,
                        "format": "wav"
                    }
                })
            
            messages.append({"role": "user", "content": content})
        
        # Add assistant seed if present
        if request.assistant_text:
            messages.append({"role": "assistant", "content": request.assistant_text})
        
        return messages
    
    def _convert_tools(self, tools: Any) -> List[Dict]:
        """Convert tools to Responses API format."""
        if isinstance(tools, str) and tools in self.NATIVE_TOOLS:
            # Native tool
            return [{"type": tools}]
        elif isinstance(tools, list):
            # List of tools
            converted = []
            for tool in tools:
                if isinstance(tool, str) and tool in self.NATIVE_TOOLS:
                    converted.append({"type": tool})
                elif isinstance(tool, dict):
                    # Custom tool - internally tagged format
                    if "type" in tool and tool["type"] == "function":
                        # Convert from Chat Completions format if needed
                        if "function" in tool:
                            # External tagging (Chat Completions)
                            func = tool["function"]
                            converted.append({
                                "type": "function",
                                "name": func["name"],
                                "description": func.get("description", ""),
                                "parameters": func.get("parameters", {})
                            })
                        else:
                            # Already internal tagging (Responses)
                            converted.append(tool)
                    else:
                        converted.append(tool)
            return converted
        elif isinstance(tools, dict):
            return [tools]
        else:
            return []
    
    def _build_json_schema(self, schema_model: Type, strict: bool = True) -> Dict:
        """Convert Pydantic model to JSON Schema for Structured Outputs."""
        from pydantic import BaseModel
        
        # Ensure it's a Pydantic model
        if not issubclass(schema_model, BaseModel):
            raise ValueError(f"response_schema must be a Pydantic BaseModel, got {type(schema_model)}")
        
        # Generate JSON schema with proper configuration for strict mode
        schema = schema_model.model_json_schema(mode='serialization')
        
        # For strict mode, we need to ensure all properties are required
        # and additionalProperties is false
        if strict:
            schema['additionalProperties'] = False
            # Make all properties required (even Optional ones)
            if 'properties' in schema:
                schema['required'] = list(schema['properties'].keys())
            # Also set it recursively for nested objects
            self._set_additional_properties_false(schema)
        
        # Build Structured Output format specification
        return {
            "type": "json_schema",
            "name": schema_model.__name__.lower(),
            "schema": schema,
            "strict": strict
        }
    
    def _set_additional_properties_false(self, schema: Dict):
        """Recursively set additionalProperties to false and all properties to required."""
        if isinstance(schema, dict):
            if schema.get('type') == 'object':
                schema['additionalProperties'] = False
                # Make all properties required in nested objects too
                if 'properties' in schema:
                    schema['required'] = list(schema['properties'].keys())
                    # Clean up $ref fields - they can't have description
                    for prop_name, prop_schema in schema['properties'].items():
                        if '$ref' in prop_schema and 'description' in prop_schema:
                            # Keep only the $ref, remove description
                            schema['properties'][prop_name] = {'$ref': prop_schema['$ref']}
            
            # Handle nested definitions
            if '$defs' in schema:
                for def_schema in schema['$defs'].values():
                    self._set_additional_properties_false(def_schema)
            
            # Process nested schemas
            for key, value in schema.items():
                if key not in ['$defs']:  # Skip already processed defs
                    if isinstance(value, dict):
                        self._set_additional_properties_false(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                self._set_additional_properties_false(item)
    
    def _invoke_impl(self, payload: Dict) -> Tuple[Any, bool, Optional[ErrorType]]:
        """Core synchronous invoke logic for Responses API."""
        try:
            response = self.client.responses.create(**payload)
            return response, True, None
        except RateLimitError as e:
            self.logger.warning(f"Rate limit hit: {e}")
            raise  # Let retry logic handle it
        except PermissionDeniedError as e:
            self.logger.error(f"Permission denied: {e}")
            if "unsupported_country_region_territory" in str(e):
                return None, False, ErrorType.UNSUPPORTED_REGION
            elif "insufficient_quota" in str(e):
                return None, False, ErrorType.INSUFFICIENT_QUOTA
            else:
                return None, False, ErrorType.UNKNOWN_OPENAI_ERROR
        except Exception as e:
            self.logger.error(f"Unexpected error in Responses API: {e}")
            raise
    
    async def _invoke_async_impl(self, payload: Dict) -> Tuple[Any, bool, Optional[ErrorType]]:
        """Core asynchronous invoke logic for Responses API."""
        try:
            # Use async client for async calls
            response = await self.async_client.responses.create(**payload)
            return response, True, None
        except RateLimitError as e:
            self.logger.warning(f"Rate limit hit: {e}")
            raise  # Let retry logic handle it
        except PermissionDeniedError as e:
            self.logger.error(f"Permission denied: {e}")
            if "unsupported_country_region_territory" in str(e):
                return None, False, ErrorType.UNSUPPORTED_REGION
            elif "insufficient_quota" in str(e):
                return None, False, ErrorType.INSUFFICIENT_QUOTA
            else:
                return None, False, ErrorType.UNKNOWN_OPENAI_ERROR
        except Exception as e:
            self.logger.error(f"Unexpected error in Responses API: {e}")
            raise
    
    def extract_usage(self, response: Any) -> Dict[str, Any]:
        """Extract usage metadata from Responses API response."""
        if not response:
            return {}
        
        usage = {}
        
        # Extract token counts from response.usage
        if hasattr(response, 'usage'):
            usage['input_tokens'] = getattr(response.usage, 'input_tokens', 0)
            usage['output_tokens'] = getattr(response.usage, 'output_tokens', 0)
            usage['reasoning_tokens'] = getattr(response.usage, 'reasoning_tokens', 0)
            usage['total_tokens'] = (
                usage['input_tokens'] + 
                usage['output_tokens'] + 
                usage['reasoning_tokens']
            )
        
        # Extract the actual text content using output_text helper
        if hasattr(response, 'output_text'):
            usage['content'] = response.output_text
        elif hasattr(response, 'output') and response.output:
            # Fallback to parsing output items
            for item in response.output:
                if item.type == "message" and item.content:
                    for content_item in item.content:
                        if content_item.get("type") == "output_text":
                            usage['content'] = content_item.get("text", "")
                            break
        
        # Store response ID for CoT chaining
        if hasattr(response, 'id'):
            usage['response_id'] = response.id
        
        # Store if response was stored
        if hasattr(response, 'stored'):
            usage['stored'] = response.stored
        
        return usage
    
    def calculate_cost(self, model: str, usage: Dict[str, Any]) -> Dict[str, float]:
        """Calculate costs including reasoning tokens."""
        costs = self.MODEL_COSTS.get(model, {
            'input_token_cost': 0,
            'output_token_cost': 0,
            'reasoning_token_cost': 0
        })
        
        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)
        reasoning_tokens = usage.get('reasoning_tokens', 0)
        
        input_cost = input_tokens * costs['input_token_cost']
        output_cost = output_tokens * costs['output_token_cost']
        reasoning_cost = reasoning_tokens * costs.get('reasoning_token_cost', 0)
        
        return {
            'input_cost': input_cost,
            'output_cost': output_cost,
            'reasoning_cost': reasoning_cost,
            'total_cost': input_cost + output_cost + reasoning_cost
        }


def main():
    """Test the Responses API provider with various scenarios."""
    import asyncio
    import json
    from dotenv import load_dotenv
    from ..schemas import LLMCallRequest
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Setup logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    print("=" * 60)
    print("Testing OpenAI Responses API Provider")
    print("=" * 60)
    
    # Initialize provider with GPT-5 (or fall back to gpt-4 if not available)
    # Note: GPT-5 may not be available yet, so we'll test with gpt-4 models
    # that should work with Responses API according to migration guide
    model = "gpt-4o-mini"  # Using a model that exists and should work with Responses API
    
    try:
        provider = ResponsesAPIProvider(model_name=model, logger=logger)
        print(f"✓ Initialized provider with model: {model}")
    except Exception as e:
        print(f"✗ Failed to initialize provider: {e}")
        return
    
    # Test 1: Simple text generation
    print("\n" + "=" * 60)
    print("Test 1: Simple Text Generation")
    print("=" * 60)
    
    request1 = LLMCallRequest(
        model_name=model,
        user_prompt="Write a haiku about Python programming",
        system_prompt="You are a creative poet who loves coding"
    )
    
    try:
        payload1 = provider.convert_request(request1)
        print(f"Payload: {json.dumps(payload1, indent=2)}")
        
        response1, success1, error1 = provider._invoke_impl(payload1)
        
        if success1:
            print(f"✓ Response received!")
            print(f"Response ID: {response1.id}")
            print(f"Output: {response1.output_text}")
            
            # Extract usage
            usage1 = provider.extract_usage(response1)
            print(f"Tokens - Input: {usage1.get('input_tokens', 0)}, "
                  f"Output: {usage1.get('output_tokens', 0)}, "
                  f"Reasoning: {usage1.get('reasoning_tokens', 0)}")
            
            # Calculate cost
            cost1 = provider.calculate_cost(model, usage1)
            print(f"Cost: ${cost1['total_cost']:.6f}")
            
            # Store response ID for next test
            first_response_id = response1.id
        else:
            print(f"✗ Request failed with error: {error1}")
            first_response_id = None
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        first_response_id = None
    
    # Test 2: CoT chaining with previous_response_id
    if first_response_id:
        print("\n" + "=" * 60)
        print("Test 2: Chain-of-Thought with previous_response_id")
        print("=" * 60)
        
        request2 = LLMCallRequest(
            model_name=model,
            user_prompt="Now explain what makes that haiku good"
            # Note: previous_response_id would be added if field exists in schema
        )
        # Manually add previous_response_id for testing
        request2.previous_response_id = first_response_id
        
        try:
            payload2 = provider.convert_request(request2)
            print(f"Using previous_response_id: {first_response_id}")
            
            response2, success2, error2 = provider._invoke_impl(payload2)
            
            if success2:
                print(f"✓ Chained response received!")
                print(f"Output: {response2.output_text}")
                
                usage2 = provider.extract_usage(response2)
                print(f"Tokens (should be less due to CoT): "
                      f"Reasoning: {usage2.get('reasoning_tokens', 0)}")
        except Exception as e:
            print(f"✗ Test 2 failed: {e}")
    
    # Test 3: Different reasoning efforts
    print("\n" + "=" * 60)
    print("Test 3: Reasoning Effort Comparison")
    print("=" * 60)
    
    for effort in ["minimal", "low", "high"]:
        print(f"\nTesting with {effort} reasoning effort:")
        
        request3 = LLMCallRequest(
            model_name=model,
            user_prompt="What is 25 * 37?"
        )
        # Manually add reasoning_effort for testing
        request3.reasoning_effort = effort
        
        try:
            payload3 = provider.convert_request(request3)
            response3, success3, error3 = provider._invoke_impl(payload3)
            
            if success3:
                usage3 = provider.extract_usage(response3)
                print(f"  {effort}: {usage3.get('reasoning_tokens', 0)} reasoning tokens")
                print(f"  Answer: {response3.output_text}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
    
    # Test 4: Native tools (web search)
    print("\n" + "=" * 60)
    print("Test 4: Native Web Search Tool")
    print("=" * 60)
    
    request4 = LLMCallRequest(
        model_name=model,
        user_prompt="What's the current weather in San Francisco?",
        tool_call="web_search"  # Use native web search
    )
    
    try:
        payload4 = provider.convert_request(request4)
        print(f"Tools in payload: {payload4.get('tools', [])}")
        
        response4, success4, error4 = provider._invoke_impl(payload4)
        
        if success4:
            print(f"✓ Tool response received!")
            print(f"Output: {response4.output_text}")
    except Exception as e:
        print(f"✗ Test 4 failed: {e}")
    
    # Test 5: Async test
    print("\n" + "=" * 60)
    print("Test 5: Async Generation")
    print("=" * 60)
    
    async def test_async():
        request5 = LLMCallRequest(
            model_name=model,
            user_prompt="Count from 1 to 5 in Spanish"
        )
        # Manually add verbosity for testing
        request5.verbosity = "low"
        
        payload5 = provider.convert_request(request5)
        response5, success5, error5 = await provider._invoke_async_impl(payload5)
        
        if success5:
            print(f"✓ Async response received!")
            print(f"Output: {response5.output_text}")
        else:
            print(f"✗ Async failed: {error5}")
    
    try:
        asyncio.run(test_async())
    except Exception as e:
        print(f"✗ Test 5 failed: {e}")
    
    print("\n" + "=" * 60)
    print("Testing Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
    
    