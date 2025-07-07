# llmservice/providers/ollama_provider.py
"""
Ollama provider implementation for local models.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from langchain_ollama import OllamaLLM

from .base import BaseLLMProvider
from ..schemas import LLMCallRequest, ErrorType


class OllamaProvider(BaseLLMProvider):
    """Ollama provider for local models."""
    
    # Common Ollama models (extend as needed)
    SUPPORTED_MODELS = {
        "llama3", "llama3.1", "llama3.2", "llama2", "llama2:7b", "llama2:13b",
        "mistral", "mistral:7b", "mistral-nemo", "mixtral", "mixtral:8x7b",
        "codellama", "codellama:7b", "codellama:13b", "codellama:34b",
        "phi3", "phi3:mini", "phi3:medium",
        "qwen2", "qwen2:7b", "qwen2:14b",
        "gemma2", "gemma2:2b", "gemma2:9b", "gemma2:27b",
        "deepseek-coder", "deepseek-coder:6.7b", "deepseek-coder:33b",
        "solar", "solar:10.7b",
        "vicuna", "vicuna:7b", "vicuna:13b",
        "orca-mini", "orca-mini:3b", "orca-mini:7b",
        "neural-chat", "neural-chat:7b",
        "starling-lm", "starling-lm:7b"
    }
    
    def __init__(self, model_name: str, logger: Optional[logging.Logger] = None):
        super().__init__(model_name, logger)
        self.client = OllamaLLM(model=model_name)
        
        # Validate model availability on initialization
        if not self._check_model_availability():
            self.logger.warning(f"Ollama model '{model_name}' may not be downloaded. "
                              f"Run 'ollama pull {model_name}' if needed.")
    
    @classmethod
    def supports_model(cls, model_name: str) -> bool:
        """Check if this provider supports the given model."""
        # Support explicit models in our list
        if model_name in cls.SUPPORTED_MODELS:
            return True
        
        # Also support common model name patterns for Ollama
        ollama_patterns = [
            "llama", "mistral", "codellama", "phi", "qwen", "gemma", 
            "deepseek", "solar", "vicuna", "orca", "neural", "starling"
        ]
        return any(pattern in model_name.lower() for pattern in ollama_patterns)
    
    def _check_model_availability(self) -> bool:
        """
        Check if the Ollama model is available locally.
        This is a basic check - could be enhanced to actually query Ollama.
        """
        try:
            # Try a simple test prompt to see if model responds
            test_response = self.client.invoke("test")
            return True
        except Exception as e:
            self.logger.debug(f"Model availability check failed: {e}")
            return False
    
    def convert_request(self, request: LLMCallRequest) -> str:
        """Convert LLMCallRequest to Ollama-compatible prompt string."""
        prompt_parts = []
        
        if request.system_prompt:
            prompt_parts.append(f"System: {request.system_prompt}")
        
        if request.user_prompt:
            prompt_parts.append(f"User: {request.user_prompt}")
        
        # For now, ignore audio/images/tools in Ollama
        # Could be extended to handle them differently or warn user
        if request.input_audio_b64:
            self.logger.warning("Audio input not supported in Ollama provider")
        
        if request.images:
            self.logger.warning("Image input not supported in Ollama provider")
        
        if request.tool_call:
            self.logger.warning("Tool calls not supported in Ollama provider")
        
        return "\n\n".join(prompt_parts) if prompt_parts else ""
    
    def _invoke_impl(self, payload: str) -> Tuple[Any, bool, Optional[ErrorType]]:
        """Core Ollama sync invoke logic."""
        try:
            if not payload:
                raise ValueError("Empty prompt provided to Ollama")
            
            response = self.client.invoke(payload)
            return response, True, None
        except Exception as e:
            self.logger.error(f"Ollama invoke error: {e}")
            raise
    
    async def _invoke_async_impl(self, payload: str) -> Tuple[Any, bool, Optional[ErrorType]]:
        """Core Ollama async invoke logic."""
        try:
            if not payload:
                raise ValueError("Empty prompt provided to Ollama")
            
            if not hasattr(self.client, "ainvoke"):
                raise NotImplementedError(f"{type(self.client).__name__} does not support async")
            
            response = await self.client.ainvoke(payload)
            return response, True, None
        except Exception as e:
            self.logger.error(f"Ollama async invoke error: {e}")
            raise
    
    def extract_usage(self, response: Any) -> Dict[str, Any]:
        """
        Ollama typically doesn't provide usage stats.
        Could estimate based on response length if needed.
        """
        # Basic estimation based on response content
        if hasattr(response, 'content') and response.content:
            # Rough estimation: ~4 characters per token
            estimated_output_tokens = len(response.content) // 4
        elif isinstance(response, str):
            estimated_output_tokens = len(response) // 4
        else:
            estimated_output_tokens = 0
        
        return {
            "input_tokens": 0,  # Ollama doesn't provide this
            "output_tokens": estimated_output_tokens,
            "total_tokens": estimated_output_tokens
        }
    
    def calculate_cost(self, usage: Dict[str, Any]) -> Tuple[float, float]:
        """Ollama is typically free/local."""
        return 0.0, 0.0
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Ollama model information."""
        base_info = super().get_model_info()
        
        return {
            **base_info,
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "has_cost_tracking": False,
            "is_local": True,
            "supports_streaming": True  # Most Ollama models support streaming
        }
    
    def validate_model(self) -> bool:
        """Validate that the Ollama model is available and ready."""
        if not self.supports_model(self.model_name):
            return False
        
        return self._check_model_availability()