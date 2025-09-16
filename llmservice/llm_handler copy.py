# llmservice/llm_handler.py
"""
Refactored LLM Handler with clean provider abstraction.
"""

import os
import logging
from typing import Any, Dict, List, Optional, Tuple, Type
from datetime import timedelta
import asyncio

# Third-party imports
from dotenv import load_dotenv
from tenacity import (
    Retrying, AsyncRetrying, retry_if_exception_type, 
    stop_after_attempt, wait_random_exponential
)
import httpx
from openai import RateLimitError

# Local imports
from .schemas import LLMCallRequest, InvokeResponseData, InvocationAttempt, ErrorType
from .utils import _now_dt
from .providers import BaseLLMProvider, OpenAIProvider, OllamaProvider

# Load environment variables
load_dotenv()

# Configure logging to reduce noise
logging.getLogger("langchain_community.llms").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# ============================================================================
# Main LLM Handler
# ============================================================================

class LLMHandler:
    """Clean, provider-agnostic LLM handler with automatic provider detection."""
    
    # Provider registry
    PROVIDERS: Dict[str, Type[BaseLLMProvider]] = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
    }
    
    def __init__(self, model_name: str, logger: Optional[logging.Logger] = None):
        self.model_name = model_name
        self.logger = logger or logging.getLogger(__name__)
        self.max_retries = 2
        
        # Auto-detect and initialize the appropriate provider
        provider_name = self._detect_provider(model_name)
        provider_class = self.PROVIDERS[provider_name]
        self.provider = provider_class(model_name, logger)
        
        self.logger.debug(f"Initialized LLMHandler with {provider_name} provider for model {model_name}")
    
    def _detect_provider(self, model_name: str) -> str:
        """Auto-detect which provider to use for a given model."""
        for provider_name, provider_class in self.PROVIDERS.items():
            if provider_class.supports_model(model_name):
                return provider_name
        
        # Fallback logic for unknown models
        if model_name.startswith(("gpt-", "o1", "o3", "o4")):
            self.logger.warning(f"Unknown OpenAI model '{model_name}', using OpenAI provider")
            return "openai"
        else:
            self.logger.warning(f"Unknown model '{model_name}', using Ollama provider")
            return "ollama"
    
    def change_model(self, model_name: str) -> None:
        """Switch to a different model (potentially different provider)."""
        if model_name == self.model_name:
            return  # No change needed
        
        self.model_name = model_name
        provider_name = self._detect_provider(model_name)
        provider_class = self.PROVIDERS[provider_name]
        self.provider = provider_class(model_name, self.logger)
        
        # self.logger.debug(f"Changed to model {model_name} with {provider_name} provider")
    
    def process_call_request(self, request: LLMCallRequest) -> InvokeResponseData:
        """Main entry point for synchronous LLM calls."""
        # Switch model if needed
        if request.model_name and request.model_name != self.model_name:
            self.change_model(request.model_name)
        
        # Convert request to provider-specific payload
        payload = self.provider.convert_request(request)
        
        # Execute with retries
        attempts = []
        final_response = None
        final_success = False
        final_error_type = None
        
        try:
            for attempt in Retrying(
                retry=retry_if_exception_type((httpx.HTTPStatusError, RateLimitError)),
                stop=stop_after_attempt(self.max_retries),
                wait=wait_random_exponential(min=1, max=60),
                reraise=True
            ):
                with attempt:
                    n = attempt.retry_state.attempt_number
                    start = _now_dt()
                    
                    try:
                        resp, success, error_type = self.provider._invoke_impl(payload)
                        final_response = resp
                        final_success = success
                        final_error_type = error_type
                    except Exception as e:
                        end = _now_dt()
                        backoff = None
                        if attempt.retry_state.next_action:
                            backoff = timedelta(seconds=attempt.retry_state.next_action.sleep)
                        
                        attempts.append(InvocationAttempt(
                            attempt_number=n,
                            invoke_start_at=start,
                            invoke_end_at=end,
                            backoff_after_ms=backoff,
                            error_message=str(e)
                        ))
                        raise
                    else:
                        end = _now_dt()
                        attempts.append(InvocationAttempt(
                            attempt_number=n,
                            invoke_start_at=start,
                            invoke_end_at=end,
                            backoff_after_ms=None,
                            error_message=None
                        ))
            
            # Build usage metadata with costs
            usage = self._build_usage_metadata(final_response, final_success)
            
            return InvokeResponseData(
                success=final_success,
                response=final_response,
                attempts=attempts,
                usage=usage,
                error_type=final_error_type
            )
            
        except Exception as final_exc:
            # All retries exhausted
            self.logger.error(f"All retries exhausted for model {self.model_name}: {final_exc}")
            usage = self._init_empty_usage()
            return InvokeResponseData(
                success=False,
                response=None,
                attempts=attempts,
                usage=usage,
                error_type=final_error_type
            )
    
    async def process_call_request_async(self, request: LLMCallRequest) -> InvokeResponseData:
        """Main entry point for asynchronous LLM calls."""
        # Switch model if needed
        if request.model_name and request.model_name != self.model_name:
            self.change_model(request.model_name)
        
        # Convert request to provider-specific payload
        payload = self.provider.convert_request(request)
        
        # Execute with retries
        attempts = []
        final_response = None
        final_success = False
        final_error_type = None
        
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type((httpx.HTTPStatusError, RateLimitError)),
                stop=stop_after_attempt(self.max_retries),
                wait=wait_random_exponential(min=1, max=60),
                reraise=True
            ):
                with attempt:
                    n = attempt.retry_state.attempt_number
                    start = _now_dt()
                    
                    try:
                        resp, success, error_type = await self.provider._invoke_async_impl(payload)
                        final_response = resp
                        final_success = success
                        final_error_type = error_type
                    except Exception as e:
                        end = _now_dt()
                        backoff = None
                        if attempt.retry_state.next_action:
                            backoff = timedelta(seconds=attempt.retry_state.next_action.sleep)
                        
                        attempts.append(InvocationAttempt(
                            attempt_number=n,
                            invoke_start_at=start,
                            invoke_end_at=end,
                            backoff_after_ms=backoff,
                            error_message=str(e)
                        ))
                        raise
                    else:
                        end = _now_dt()
                        attempts.append(InvocationAttempt(
                            attempt_number=n,
                            invoke_start_at=start,
                            invoke_end_at=end,
                            backoff_after_ms=None,
                            error_message=None
                        ))
            
            # Build usage metadata with costs
            usage = self._build_usage_metadata(final_response, final_success)
            
            return InvokeResponseData(
                success=final_success,
                response=final_response,
                attempts=attempts,
                usage=usage,
                error_type=final_error_type
            )
            
        except Exception as final_exc:
            # All retries exhausted
            self.logger.error(f"All async retries exhausted for model {self.model_name}: {final_exc}")
            usage = self._init_empty_usage()
            return InvokeResponseData(
                success=False,
                response=None,
                attempts=attempts,
                usage=usage,
                error_type=final_error_type
            )
    
    def _build_usage_metadata(self, response: Any, success: bool) -> Dict[str, Any]:
        """Build comprehensive usage metadata with costs."""
        if not success or not response:
            return self._init_empty_usage()
        
        # Extract basic usage from provider
        usage = self.provider.extract_usage(response)
        
        # Calculate costs
        input_cost, output_cost = self.provider.calculate_cost(usage)
        
        # Build complete metadata
        return {
            **usage,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": input_cost + output_cost
        }
    
    def _init_empty_usage(self) -> Dict[str, Any]:
        """Return empty usage metadata structure."""
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "input_cost": 0.0,
            "output_cost": 0.0,
            "total_cost": 0.0
        }


# ============================================================================
# Testing/Example Usage
# ============================================================================

def main():
    """Example usage of the refactored LLMHandler."""
    import base64
    from pathlib import Path
    
    logging.basicConfig(level=logging.DEBUG)
    
    # Test 1: Basic OpenAI model
    print("=== Testing Basic OpenAI Model ===")
    handler = LLMHandler("gpt-4o-mini")
    
    request = LLMCallRequest(
        model_name="gpt-4o-mini",
        user_prompt="What is the capital of France?"
    )
    
    result = handler.process_call_request(request)
    print(f"Success: {result.success}")
    if result.success:
        print(f"Response: {result.response.content}")
        print(f"Usage: {result.usage}")
    else:
        print(f"Error: {result.error_type}")
    
    # Test 2: Audio input (multimodal)
    print("\n=== Testing Audio Input (Multimodal) ===")
    try:
        # Switch to audio-capable model
        handler.change_model("gpt-4o-audio-preview")
        
        wav_path = Path("llmservice/my_voice.wav")
        if wav_path.exists():
            # Read and base64-encode the audio file
            b64_wav = base64.b64encode(wav_path.read_bytes()).decode("ascii")
            
            # Create audio request using new interface
            audio_request = LLMCallRequest(
                model_name="gpt-4o-audio-preview",
                user_prompt="Please answer the question in the audio:",
                input_audio_b64=b64_wav
            )
            
            audio_result = handler.process_call_request(audio_request)
            print(f"Audio Success: {audio_result.success}")
            if audio_result.success:
                print(f"Audio Response: {audio_result.response.content}")
                print(f"Audio Usage: {audio_result.usage}")
            else:
                print(f"Audio Error: {audio_result.error_type}")
        else:
            print(f"Audio file not found at {wav_path.resolve()}")
            print("To test audio, place a WAV file at that location.")
            
    except Exception as e:
        print(f"Audio test failed: {e}")
    
    # Test 3: System + User prompt combination
    print("\n=== Testing System + User Prompt ===")
    
    system_user_request = LLMCallRequest(
        model_name="gpt-4o-mini",
        system_prompt="You are a helpful math tutor. Always show your work.",
        user_prompt="What is 15 * 23?"
    )
    
    system_result = handler.process_call_request(system_user_request)
    print(f"System+User Success: {system_result.success}")
    if system_result.success:
        print(f"Response: {system_result.response.content}")

    # Test 4: Audio Output (Text-to-Speech)
    print("\n=== Testing Audio Output (Text-to-Speech) ===")
    try:
        # Test with audio output
        audio_output_request = LLMCallRequest(
            model_name="gpt-4o-audio-preview",
            user_prompt="Please say 'Hello, this is a test of audio output' in a friendly voice.",
            output_data_format="audio",  # Request audio output
            audio_output_config={"voice": "alloy", "format": "wav"}  # Optional config
        )
        
        audio_output_result = handler.process_call_request(audio_output_request)
        print(f"Audio Output Success: {audio_output_result.success}")
        
        if audio_output_result.success:
            print(f"Audio Output Usage: {audio_output_result.usage}")
            
            # Save comprehensive response info to file
            response = audio_output_result.response
            log_file = Path("llmservice/audio_response_debug.txt")
            
            with open(log_file, "w") as f:
                f.write("=== AUDIO OUTPUT RESPONSE DEBUG ===\n\n")
                f.write(f"Response type: {type(response)}\n")
                f.write(f"Response class: {response.__class__}\n\n")
                
                # Write all attributes
                f.write("=== RESPONSE ATTRIBUTES ===\n")
                for attr in dir(response):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(response, attr)
                            if callable(value):
                                f.write(f"{attr}: <method>\n")
                            else:
                                f.write(f"{attr}: {type(value)} = {repr(value)}\n")
                        except Exception as e:
                            f.write(f"{attr}: <error getting value: {e}>\n")
                
                # Special focus on important attributes
                f.write("\n=== DETAILED ATTRIBUTE INSPECTION ===\n")
                
                # Content
                if hasattr(response, 'content'):
                    f.write(f"content type: {type(response.content)}\n")
                    f.write(f"content value: {repr(response.content)}\n\n")
                
                # Response metadata
                if hasattr(response, 'response_metadata'):
                    f.write(f"response_metadata type: {type(response.response_metadata)}\n")
                    f.write(f"response_metadata: {response.response_metadata}\n\n")
                
                # Usage metadata
                if hasattr(response, 'usage_metadata'):
                    f.write(f"usage_metadata type: {type(response.usage_metadata)}\n")
                    f.write(f"usage_metadata: {response.usage_metadata}\n\n")
                
                # Additional kwargs (where audio might be hiding)
                if hasattr(response, 'additional_kwargs'):
                    f.write(f"additional_kwargs type: {type(response.additional_kwargs)}\n")
                    f.write(f"additional_kwargs: {response.additional_kwargs}\n\n")
                
                # Try to access the raw response if available
                if hasattr(response, '_raw_response'):
                    f.write(f"_raw_response: {response._raw_response}\n\n")
                
                # Check if there's a choices attribute
                if hasattr(response, 'choices'):
                    f.write(f"choices: {response.choices}\n\n")
                
                # Full object representation
                f.write("=== FULL OBJECT REPR ===\n")
                f.write(f"{repr(response)}\n")
            
            print(f"📝 Full response debug saved to: {log_file.resolve()}")
            
            # Check if response has audio data in the correct location
            audio_found = False
            
            # Check additional_kwargs for audio (this is where it actually is!)
            if hasattr(response, 'additional_kwargs') and isinstance(response.additional_kwargs, dict):
                if 'audio' in response.additional_kwargs:
                    audio_info = response.additional_kwargs['audio']
                    if isinstance(audio_info, dict) and 'data' in audio_info:
                        print("✅ Audio data found in response.additional_kwargs['audio']['data']")
                        print(f"Audio transcript: {audio_info.get('transcript', 'No transcript')}")
                        
                        try:
                            # Decode base64 audio data
                            audio_data = audio_info['data']
                            audio_bytes = base64.b64decode(audio_data)
                            
                            output_path = Path("llmservice/test_audio_output.wav")
                            output_path.write_bytes(audio_bytes)
                            print(f"✅ Audio saved to: {output_path.resolve()}")
                            print(f"Audio size: {len(audio_bytes)} bytes")
                            audio_found = True
                        except Exception as save_error:
                            print(f"⚠️ Could not save audio: {save_error}")
                    else:
                        print("✅ Audio found in additional_kwargs but no 'data' field")
            
            # Fallback: Check response_metadata for audio
            if not audio_found and hasattr(response, 'response_metadata') and isinstance(response.response_metadata, dict):
                if 'audio' in response.response_metadata:
                    print("✅ Audio found in response_metadata")
                    audio_found = True
            
            # Legacy check: response.content (probably won't find anything now)
            if not audio_found and hasattr(response, 'content') and isinstance(response.content, dict) and 'audio' in response.content:
                audio_info = response.content['audio']
                if isinstance(audio_info, dict) and 'data' in audio_info:
                    print("✅ Audio data found in response.content['audio']['data']")
                    audio_found = True
            
            if not audio_found:
                print("⚠️ No audio data found - check the debug file for details")
        else:
            print(f"Audio Output Error: {audio_output_result.error_type}")
            
    except Exception as e:
        print(f"Audio output test failed: {e}")

    # Test 5: Both Text and Audio Output
    print("\n=== Testing Both Text and Audio Output ===")
    try:
        both_output_request = LLMCallRequest(
            model_name="gpt-4o-audio-preview",
            user_prompt="Explain what AI is in simple terms.",
            output_data_format="both",  # Request both text and audio
            audio_output_config={"voice": "shimmer", "format": "wav"}
        )
        
        both_result = handler.process_call_request(both_output_request)
        print(f"Both Output Success: {both_result.success}")
        
        if both_result.success:
            response = both_result.response
            
            # Save "both" mode response to file too
            log_file_both = Path("llmservice/both_response_debug.txt")
            
            with open(log_file_both, "w") as f:
                f.write("=== BOTH MODE RESPONSE DEBUG ===\n\n")
                f.write(f"Response type: {type(response)}\n")
                f.write(f"Response class: {response.__class__}\n\n")
                
                # Write all attributes
                f.write("=== RESPONSE ATTRIBUTES ===\n")
                for attr in dir(response):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(response, attr)
                            if callable(value):
                                f.write(f"{attr}: <method>\n")
                            else:
                                f.write(f"{attr}: {type(value)} = {repr(value)}\n")
                        except Exception as e:
                            f.write(f"{attr}: <error getting value: {e}>\n")
                
                f.write("\n=== DETAILED INSPECTION ===\n")
                
                if hasattr(response, 'content'):
                    f.write(f"content: {repr(response.content)}\n\n")
                if hasattr(response, 'response_metadata'):
                    f.write(f"response_metadata: {response.response_metadata}\n\n")
                if hasattr(response, 'additional_kwargs'):
                    f.write(f"additional_kwargs: {response.additional_kwargs}\n\n")
                
                f.write(f"Full repr: {repr(response)}\n")
            
            print(f"📝 Both mode response debug saved to: {log_file_both.resolve()}")
            
            # Check text output
            if hasattr(response, 'content'):
                if isinstance(response.content, str):
                    print(f"✅ Text received: {response.content[:100]}...")
                elif isinstance(response.content, dict):
                    # Extract text from dict structure
                    text_content = response.content.get('text', response.content.get('content', ''))
                    if text_content:
                        print(f"✅ Text received: {text_content[:100]}...")
            
            # Check audio output in the correct location (additional_kwargs)
            audio_found = False
            if hasattr(response, 'additional_kwargs') and isinstance(response.additional_kwargs, dict):
                if 'audio' in response.additional_kwargs:
                    audio_info = response.additional_kwargs['audio']
                    if isinstance(audio_info, dict) and 'data' in audio_info:
                        print("✅ Audio data also received in additional_kwargs")
                        print(f"Audio transcript: {audio_info.get('transcript', 'No transcript')}")
                        
                        try:
                            # Decode and save the audio from "both" mode
                            audio_data = audio_info['data']
                            audio_bytes = base64.b64decode(audio_data)
                            
                            output_path = Path("llmservice/test_both_output.wav")
                            output_path.write_bytes(audio_bytes)
                            print(f"✅ Audio saved to: {output_path.resolve()}")
                            print(f"Audio size: {len(audio_bytes)} bytes")
                            audio_found = True
                        except Exception as save_error:
                            print(f"⚠️ Could not save audio: {save_error}")
            
            # Fallback: Check legacy location
            if not audio_found and hasattr(response, 'content') and isinstance(response.content, dict) and 'audio' in response.content:
                audio_info = response.content['audio']
                if isinstance(audio_info, dict) and 'data' in audio_info:
                    print("✅ Audio data also received in content")
                    audio_found = True
            
            if not audio_found:
                print("⚠️ No audio data found in 'both' mode response")
            
            print(f"Both Output Usage: {both_result.usage}")
        else:
            print(f"Both Output Error: {both_result.error_type}")
            
    except Exception as e:
        print(f"Both output test failed: {e}")

    # Test 6: System + User prompt combination
    print("\n=== Testing Model Switching ===")
    handler.change_model("gpt-4o")
    
    switch_request = LLMCallRequest(
        model_name="gpt-4o",
        user_prompt="Write a haiku about programming."
    )
    
    switch_result = handler.process_call_request(switch_request)
    print(f"Model Switch Success: {switch_result.success}")
    if switch_result.success:
        print(f"Haiku Response: {switch_result.response.content}")


if __name__ == "__main__":
    main()