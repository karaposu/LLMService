# llmservice/providers/openai_provider.py
"""
OpenAI provider implementation with full cost calculation and error handling.
"""

import os
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import RateLimitError, PermissionDeniedError
from langchain_openai import ChatOpenAI

from .base import BaseLLMProvider
from ..schemas import LLMCallRequest, ErrorType


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation with full cost calculation."""
    
    MODEL_COSTS = {
        'gpt-4o-search-preview': {'input_token_cost': 2.5e-6, 'output_token_cost': 10e-6},
        'gpt-4o-mini-search-preview': {'input_token_cost': 2.5e-6, 'output_token_cost': 0.6e-6},
        'gpt-4.5-preview': {'input_token_cost': 75e-6, 'output_token_cost': 150e-6},
        'gpt-4.1-nano': {'input_token_cost': 0.1e-6, 'output_token_cost': 0.4e-6},
        'gpt-4.1-mini': {'input_token_cost': 0.4e-6, 'output_token_cost': 1.6e-6},
        'gpt-4.1': {'input_token_cost': 2e-6, 'output_token_cost': 8e-6},
        'gpt-4o': {'input_token_cost': 2.5e-6, 'output_token_cost': 10e-6},
        'gpt-4o-audio-preview': {'input_token_cost': 2.5e-6, 'output_token_cost': 10e-6},
        'gpt-4o-mini': {'input_token_cost': 0.15e-6, 'output_token_cost': 0.6e-6},
        'o1': {'input_token_cost': 15e-6, 'output_token_cost': 60e-6},
        'o1-pro': {'input_token_cost': 150e-6, 'output_token_cost': 600e-6},
        'o3': {'input_token_cost': 10e-6, 'output_token_cost': 40e-6},
        'o4-mini': {'input_token_cost': 1.1e-6, 'output_token_cost': 4.4e-6},
    }
    
    def __init__(self, model_name: str, logger: Optional[logging.Logger] = None):
        super().__init__(model_name, logger)
        self.client = self._initialize_client()
    
    @classmethod
    def supports_model(cls, model_name: str) -> bool:
        """Check if this provider supports the given model."""
        return model_name in cls.MODEL_COSTS
    
    def _initialize_client(self) -> ChatOpenAI:
        """Initialize the OpenAI client with model-specific configuration."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        if self.model_name == "gpt-4o-search-preview":
            return ChatOpenAI(
                api_key=api_key,
                model_name=self.model_name,
                model_kwargs={
                    "web_search_options": {
                        "search_context_size": "high"
                    }
                }
            )
        else:
            return ChatOpenAI(
                api_key=api_key,
                model_name=self.model_name
            )
    
    def convert_request(self, request: LLMCallRequest) -> Dict[str, Any]:
        """Convert LLMCallRequest to OpenAI-compatible payload."""
        messages = []
        
        # Add system message
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        
        # Add user message (text only, no audio for now)
        if request.user_prompt and not request.input_audio_b64:
            messages.append({"role": "user", "content": request.user_prompt})
        
        # Add assistant seed message
        if request.assistant_text:
            messages.append({"role": "assistant", "content": request.assistant_text})
        
        # Handle audio input (multimodal)
        if request.input_audio_b64:
            content = [
                {"type": "text", "text": request.user_prompt or ""},
                {
                    "type": "input_audio",
                    "input_audio": {"data": request.input_audio_b64, "format": "wav"}
                }
            ]
            messages.append({"role": "user", "content": content})
        
        # Handle images
        if request.images:
            for img_b64 in request.images:
                content = [{
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                }]
                messages.append({"role": "user", "content": content})
        
        # Handle tool calls
        if request.tool_call:
            messages.append({"role": "tool", **request.tool_call})
        
        # Build the base payload
        payload = {"messages": messages}
        
        # Configure audio output if requested
        if request.output_data_format in ("audio", "both"):
            # Default audio config if none provided
            audio_config = request.audio_output_config or {"voice": "alloy", "format": "wav"}
            
            # OpenAI only supports ["text"] or ["text", "audio"] modalities
            # Even for audio-only output, we need to include "text"
            payload["modalities"] = ["text", "audio"]
            payload["audio"] = audio_config
        
        return payload
    
    def _invoke_impl(self, payload: Dict[str, Any]) -> Tuple[Any, bool, Optional[ErrorType]]:
        """Core OpenAI sync invoke logic with error handling."""
        try:
            # Extract messages and other parameters
            messages = payload["messages"]
            
            # Check if we need to use advanced features
            if "modalities" in payload or "audio" in payload:
                # For audio features, we need to create a temporary client with the right config
                from langchain_openai import ChatOpenAI
                import os
                
                model_kwargs = {}
                if "modalities" in payload:
                    model_kwargs["modalities"] = payload["modalities"]
                if "audio" in payload:
                    model_kwargs["audio"] = payload["audio"]
                
                # Create a temporary client with audio configuration
                temp_client = ChatOpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model_name=self.model_name,
                    model_kwargs=model_kwargs
                )
                response = temp_client.invoke(messages)
            else:
                # Use standard client for non-audio requests
                response = self.client.invoke(messages)
            
            return response, True, None
            
        except RateLimitError as e:
            return self._handle_rate_limit_error(e)
        except httpx.HTTPStatusError as e:
            return self._handle_http_error(e)
        except PermissionDeniedError as e:
            return self._handle_permission_error(e)
        except Exception as e:
            self.logger.error(f"OpenAI invoke error: {e}")
            raise
    
    async def _invoke_async_impl(self, payload: Dict[str, Any]) -> Tuple[Any, bool, Optional[ErrorType]]:
        """Core OpenAI async invoke logic with error handling."""
        try:
            # Extract messages and other parameters
            messages = payload["messages"]
            
            # Check if we need to use advanced features
            if "modalities" in payload or "audio" in payload:
                # For audio features, we need to create a temporary client with the right config
                from langchain_openai import ChatOpenAI
                import os
                
                model_kwargs = {}
                if "modalities" in payload:
                    model_kwargs["modalities"] = payload["modalities"]
                if "audio" in payload:
                    model_kwargs["audio"] = payload["audio"]
                
                # Create a temporary client with audio configuration
                temp_client = ChatOpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model_name=self.model_name,
                    model_kwargs=model_kwargs
                )
                
                if not hasattr(temp_client, "ainvoke"):
                    raise NotImplementedError(f"{type(temp_client).__name__} does not support async")
                
                response = await temp_client.ainvoke(messages)
            else:
                # Use standard client for non-audio requests
                if not hasattr(self.client, "ainvoke"):
                    raise NotImplementedError(f"{type(self.client).__name__} does not support async")
                response = await self.client.ainvoke(messages)
            
            return response, True, None
            
        except RateLimitError as e:
            return self._handle_rate_limit_error(e)
        except httpx.HTTPStatusError as e:
            return self._handle_http_error(e)
        except PermissionDeniedError as e:
            return self._handle_permission_error(e)
        except Exception as e:
            self.logger.error(f"OpenAI async invoke error: {e}")
            raise
    
    def _handle_rate_limit_error(self, e: RateLimitError) -> Tuple[str, bool, ErrorType]:
        """Handle OpenAI rate limit errors."""
        error_message = str(e)
        error_code = getattr(e, "code", None)
        
        if not error_code and hasattr(e, "json_body") and e.json_body:
            error_code = e.json_body.get("error", {}).get("code")
        if not error_code and "insufficient_quota" in error_message:
            error_code = "insufficient_quota"
        
        if error_code == "insufficient_quota":
            self.logger.error("OpenAI credit is finished.")
            return "OpenAI credit is finished.", False, ErrorType.INSUFFICIENT_QUOTA
        
        self.logger.warning(f"RateLimitError: {error_message}. Retrying...")
        raise e  # Let retry mechanism handle it
    
    def _handle_http_error(self, e: httpx.HTTPStatusError) -> Tuple[str, bool, ErrorType]:
        """Handle HTTP status errors."""
        if e.response.status_code == 429:
            self.logger.warning("Rate limit exceeded: 429. Retrying...")
            raise e  # Let retry mechanism handle it
        
        self.logger.error(f"HTTP error: {e}")
        raise e
    
    def _handle_permission_error(self, e: PermissionDeniedError) -> Tuple[str, bool, ErrorType]:
        """Handle OpenAI permission errors."""
        error_code = getattr(e, "code", None)
        if error_code == "unsupported_country_region_territory":
            self.logger.error("Country/region not supported.")
            return "Country/region not supported.", False, ErrorType.UNSUPPORTED_REGION
        
        self.logger.error(f"PermissionDeniedError: {e}")
        raise e
    
    def extract_usage(self, response: Any) -> Dict[str, Any]:
        """Extract usage metadata from OpenAI response."""
        if hasattr(response, 'usage_metadata'):
            usage_meta = response.usage_metadata
            input_tokens = usage_meta.get("input_tokens", 0)
            output_tokens = usage_meta.get("output_tokens", 0)
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            }
        
        self.logger.warning("No usage_metadata found in OpenAI response")
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    
    def calculate_cost(self, usage: Dict[str, Any]) -> Tuple[float, float]:
        """Calculate costs based on OpenAI pricing."""
        cost_info = self.MODEL_COSTS.get(self.model_name)
        if not cost_info:
            self.logger.warning(f"No cost info for model: {self.model_name}")
            return 0.0, 0.0
        
        input_cost = usage["input_tokens"] * cost_info["input_token_cost"]
        output_cost = usage["output_tokens"] * cost_info["output_token_cost"]
        return input_cost, output_cost
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get OpenAI model information."""
        base_info = super().get_model_info()
        cost_info = self.MODEL_COSTS.get(self.model_name, {})
        
        return {
            **base_info,
            "input_cost_per_token": cost_info.get("input_token_cost", 0),
            "output_cost_per_token": cost_info.get("output_token_cost", 0),
            "has_cost_tracking": True
        }