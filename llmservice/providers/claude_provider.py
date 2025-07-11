# llmservice/providers/claude_provider.py
"""
Anthropic Claude provider implementation with full cost calculation and error handling.
"""

import os
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx
from anthropic import RateLimitError, PermissionDeniedError, APIStatusError
from langchain_anthropic import ChatAnthropic

from .base import BaseLLMProvider
from ..schemas import LLMCallRequest, ErrorType


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude provider implementation with full cost calculation."""
    
    # Pricing as of January 2025 (per token)
    MODEL_COSTS = {
        # Claude 3 Opus
        'claude-3-opus-20240229': {'input_token_cost': 15e-6, 'output_token_cost': 75e-6},
        'claude-3-opus': {'input_token_cost': 15e-6, 'output_token_cost': 75e-6},
        
        # Claude 3.5 Sonnet
        'claude-3-5-sonnet-20241022': {'input_token_cost': 3e-6, 'output_token_cost': 15e-6},
        'claude-3-5-sonnet-20240620': {'input_token_cost': 3e-6, 'output_token_cost': 15e-6},
        'claude-3-5-sonnet': {'input_token_cost': 3e-6, 'output_token_cost': 15e-6},
        
        # Claude 3 Sonnet
        'claude-3-sonnet-20240229': {'input_token_cost': 3e-6, 'output_token_cost': 15e-6},
        'claude-3-sonnet': {'input_token_cost': 3e-6, 'output_token_cost': 15e-6},
        
        # Claude 3.5 Haiku
        'claude-3-5-haiku-20241022': {'input_token_cost': 0.8e-6, 'output_token_cost': 4e-6},
        'claude-3-5-haiku': {'input_token_cost': 0.8e-6, 'output_token_cost': 4e-6},
        
        # Claude 3 Haiku
        'claude-3-haiku-20240307': {'input_token_cost': 0.25e-6, 'output_token_cost': 1.25e-6},
        'claude-3-haiku': {'input_token_cost': 0.25e-6, 'output_token_cost': 1.25e-6},
        
        # Claude 2 models
        'claude-2.1': {'input_token_cost': 8e-6, 'output_token_cost': 24e-6},
        'claude-2.0': {'input_token_cost': 8e-6, 'output_token_cost': 24e-6},
        'claude-2': {'input_token_cost': 8e-6, 'output_token_cost': 24e-6},
        
        # Claude Instant
        'claude-instant-1.2': {'input_token_cost': 0.8e-6, 'output_token_cost': 2.4e-6},
        'claude-instant': {'input_token_cost': 0.8e-6, 'output_token_cost': 2.4e-6},
    }
    
    # Models that support vision (images)
    VISION_MODELS = {
        'claude-3-opus-20240229', 'claude-3-opus',
        'claude-3-5-sonnet-20241022', 'claude-3-5-sonnet-20240620', 'claude-3-5-sonnet',
        'claude-3-sonnet-20240229', 'claude-3-sonnet',
        'claude-3-5-haiku-20241022', 'claude-3-5-haiku',
        'claude-3-haiku-20240307', 'claude-3-haiku'
    }
    
    def __init__(self, model_name: str, logger: Optional[logging.Logger] = None):
        super().__init__(model_name, logger)
        self.client = self._initialize_client()
    
    @classmethod
    def supports_model(cls, model_name: str) -> bool:
        """Check if this provider supports the given model."""
        # Check exact match first
        if model_name in cls.MODEL_COSTS:
            return True
        
        # Check if it starts with claude-
        if model_name.startswith('claude-'):
            return True
            
        return False
    
    def _initialize_client(self) -> ChatAnthropic:
        """Initialize the Anthropic Claude client."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        # Get optional base URL for proxy/gateway setups
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        
        client_kwargs = {
            "anthropic_api_key": api_key,
            "model_name": self.model_name,
            "max_tokens": 4096,  # Claude requires explicit max_tokens
        }
        
        if base_url:
            client_kwargs["anthropic_api_url"] = base_url
            
        return ChatAnthropic(**client_kwargs)
    
    def convert_request(self, request: LLMCallRequest) -> Dict[str, Any]:
        """Convert LLMCallRequest to Anthropic-compatible payload."""
        messages = []
        
        # Handle system message - Anthropic handles system prompts differently
        system_prompt = request.system_prompt
        
        # Add user message
        if request.user_prompt:
            # Check if we need to add images
            if request.images and self.model_name in self.VISION_MODELS:
                # For vision models, create a content array with text and images
                content = [{"type": "text", "text": request.user_prompt}]
                
                for img_b64 in request.images:
                    # Anthropic expects a specific format for images
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",  # You might want to detect this
                            "data": img_b64
                        }
                    })
                
                messages.append({"role": "user", "content": content})
            else:
                # Regular text message
                messages.append({"role": "user", "content": request.user_prompt})
        
        # Add assistant seed message if provided
        if request.assistant_text:
            messages.append({"role": "assistant", "content": request.assistant_text})
        
        # Handle audio input - Claude doesn't support audio directly
        if request.input_audio_b64:
            self.logger.warning("Claude doesn't support audio input. Ignoring audio data.")
            if not request.user_prompt:
                # If there's only audio and no text, we need to provide some context
                messages.append({
                    "role": "user", 
                    "content": "Audio input provided but not supported by Claude."
                })
        
        # Handle tool calls - Claude has a different format for tools
        if request.tool_call:
            self.logger.warning("Tool calls not yet implemented for Claude provider")
        
        # Build the payload
        payload = {
            "messages": messages,
        }
        
        # Add system prompt if provided (Anthropic uses a separate field)
        if system_prompt:
            payload["system"] = system_prompt
            
        # Check for audio output request
        if request.output_data_format in ("audio", "both"):
            self.logger.warning("Claude doesn't support audio output. Will return text only.")
        
        return payload
    
    def _invoke_impl(self, payload: Dict[str, Any]) -> Tuple[Any, bool, Optional[ErrorType]]:
        """Core Claude sync invoke logic with error handling."""
        try:
            messages = payload["messages"]
            
            # Extract system prompt if present
            kwargs = {}
            if "system" in payload:
                kwargs["system"] = payload["system"]
            
            # Invoke the model
            response = self.client.invoke(messages, **kwargs)
            return response, True, None
            
        except RateLimitError as e:
            return self._handle_rate_limit_error(e)
        except PermissionDeniedError as e:
            return self._handle_permission_error(e)
        except APIStatusError as e:
            return self._handle_api_status_error(e)
        except httpx.HTTPStatusError as e:
            return self._handle_http_error(e)
        except Exception as e:
            self.logger.error(f"Claude invoke error: {e}")
            raise
    
    async def _invoke_async_impl(self, payload: Dict[str, Any]) -> Tuple[Any, bool, Optional[ErrorType]]:
        """Core Claude async invoke logic with error handling."""
        try:
            messages = payload["messages"]
            
            # Extract system prompt if present
            kwargs = {}
            if "system" in payload:
                kwargs["system"] = payload["system"]
            
            # Check if async is supported
            if not hasattr(self.client, "ainvoke"):
                raise NotImplementedError("ChatAnthropic does not support async invocation")
            
            # Invoke the model asynchronously
            response = await self.client.ainvoke(messages, **kwargs)
            return response, True, None
            
        except RateLimitError as e:
            return self._handle_rate_limit_error(e)
        except PermissionDeniedError as e:
            return self._handle_permission_error(e)
        except APIStatusError as e:
            return self._handle_api_status_error(e)
        except httpx.HTTPStatusError as e:
            return self._handle_http_error(e)
        except Exception as e:
            self.logger.error(f"Claude async invoke error: {e}")
            raise
    
    def _handle_rate_limit_error(self, e: RateLimitError) -> Tuple[str, bool, ErrorType]:
        """Handle Claude rate limit errors."""
        error_message = str(e)
        
        # Check if it's a quota issue
        if "quota" in error_message.lower() or "credit" in error_message.lower():
            self.logger.error("Anthropic API quota exceeded.")
            return "Anthropic API quota exceeded.", False, ErrorType.INSUFFICIENT_QUOTA
        
        self.logger.warning(f"RateLimitError: {error_message}. Retrying...")
        raise e  # Let retry mechanism handle it
    
    def _handle_permission_error(self, e: PermissionDeniedError) -> Tuple[str, bool, ErrorType]:
        """Handle Claude permission errors."""
        error_message = str(e)
        
        # Check for region restrictions
        if "region" in error_message.lower() or "country" in error_message.lower():
            self.logger.error("Region/country not supported by Anthropic.")
            return "Region/country not supported by Anthropic.", False, ErrorType.UNSUPPORTED_REGION
        
        self.logger.error(f"PermissionDeniedError: {e}")
        raise e
    
    def _handle_api_status_error(self, e: APIStatusError) -> Tuple[str, bool, ErrorType]:
        """Handle Claude API status errors."""
        if e.status_code == 429:
            self.logger.warning("Rate limit exceeded: 429. Retrying...")
            raise e  # Let retry mechanism handle it
        
        self.logger.error(f"API Status Error: {e}")
        raise e
    
    def _handle_http_error(self, e: httpx.HTTPStatusError) -> Tuple[str, bool, ErrorType]:
        """Handle HTTP status errors."""
        if e.response.status_code == 429:
            self.logger.warning("Rate limit exceeded: 429. Retrying...")
            raise e  # Let retry mechanism handle it
        
        self.logger.error(f"HTTP error: {e}")
        raise e
    
    def extract_usage(self, response: Any) -> Dict[str, Any]:
        """Extract usage metadata from Claude response."""
        # LangChain's ChatAnthropic response has usage_metadata
        if hasattr(response, 'usage_metadata'):
            usage_meta = response.usage_metadata
            input_tokens = usage_meta.get("input_tokens", 0)
            output_tokens = usage_meta.get("output_tokens", 0)
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            }
        
        # Fallback: check response_metadata
        if hasattr(response, 'response_metadata'):
            usage = response.response_metadata.get('usage', {})
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            }
        
        self.logger.warning("No usage metadata found in Claude response")
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    
    def calculate_cost(self, usage: Dict[str, Any]) -> Tuple[float, float]:
        """Calculate costs based on Anthropic pricing."""
        # Try to find the model in our cost table
        cost_info = self.MODEL_COSTS.get(self.model_name)
        
        # If not found, try to match a base model name
        if not cost_info:
            # Extract base model name (e.g., "claude-3-opus" from "claude-3-opus-20240229")
            base_model = None
            for model_key in self.MODEL_COSTS:
                if self.model_name.startswith(model_key):
                    base_model = model_key
                    break
            
            if base_model:
                cost_info = self.MODEL_COSTS[base_model]
        
        if not cost_info:
            self.logger.warning(f"No cost info for model: {self.model_name}")
            return 0.0, 0.0
        
        input_cost = usage["input_tokens"] * cost_info["input_token_cost"]
        output_cost = usage["output_tokens"] * cost_info["output_token_cost"]
        return input_cost, output_cost
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Claude model information."""
        base_info = super().get_model_info()
        
        # Find cost info for this model
        cost_info = self.MODEL_COSTS.get(self.model_name, {})
        if not cost_info:
            # Try to find a matching base model
            for model_key, costs in self.MODEL_COSTS.items():
                if self.model_name.startswith(model_key):
                    cost_info = costs
                    break
        
        return {
            **base_info,
            "supports_vision": self.model_name in self.VISION_MODELS,
            "supports_audio_input": False,
            "supports_audio_output": False,
            "supports_tools": True,  # Claude supports function calling
            "max_tokens": 4096,  # Default max tokens for Claude
            "input_cost_per_token": cost_info.get("input_token_cost", 0),
            "output_cost_per_token": cost_info.get("output_token_cost", 0),
            "has_cost_tracking": bool(cost_info)
        }