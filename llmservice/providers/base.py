# llmservice/providers/base.py
"""
Abstract base class for all LLM providers.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from ..schemas import LLMCallRequest, ErrorType


class BaseLLMProvider(ABC):
    """
    Abstract base class for all LLM providers.
    
    Each provider implementation must:
    1. Define which models it supports
    2. Convert requests to provider-specific format
    3. Handle provider-specific invoke logic (sync & async)
    4. Extract usage metadata from responses
    5. Calculate costs based on provider pricing
    """
    
    def __init__(self, model_name: str, logger: Optional[logging.Logger] = None):
        self.model_name = model_name
        self.logger = logger or logging.getLogger(__name__)
    
    @classmethod
    @abstractmethod
    def supports_model(cls, model_name: str) -> bool:
        """
        Check if this provider supports the given model.
        
        Args:
            model_name: The model identifier to check
            
        Returns:
            True if this provider can handle the model, False otherwise
        """
        pass
    
    @abstractmethod
    def convert_request(self, request: LLMCallRequest) -> Any:
        """
        Convert LLMCallRequest to provider-specific payload format.
        
        Args:
            request: Standardized LLM call request
            
        Returns:
            Provider-specific payload (could be dict, string, or custom object)
        """
        pass
    
    @abstractmethod
    def _invoke_impl(self, payload: Any) -> Tuple[Any, bool, Optional[ErrorType]]:
        """
        Core synchronous invoke logic for this provider.
        
        Args:
            payload: Provider-specific payload from convert_request()
            
        Returns:
            Tuple of (response, success_flag, error_type)
            - response: Provider's raw response object
            - success_flag: True if call succeeded, False if handled error
            - error_type: ErrorType enum if error was handled, None if success
            
        Raises:
            Exception: For unhandled errors that should trigger retries
        """
        pass
    
    @abstractmethod
    async def _invoke_async_impl(self, payload: Any) -> Tuple[Any, bool, Optional[ErrorType]]:
        """
        Core asynchronous invoke logic for this provider.
        
        Args:
            payload: Provider-specific payload from convert_request()
            
        Returns:
            Tuple of (response, success_flag, error_type)
            - response: Provider's raw response object  
            - success_flag: True if call succeeded, False if handled error
            - error_type: ErrorType enum if error was handled, None if success
            
        Raises:
            Exception: For unhandled errors that should trigger retries
        """
        pass
    
    @abstractmethod
    def extract_usage(self, response: Any) -> Dict[str, Any]:
        """
        Extract usage metadata from provider's response.
        
        Args:
            response: Provider's raw response object
            
        Returns:
            Dictionary with at minimum:
            {
                "input_tokens": int,
                "output_tokens": int, 
                "total_tokens": int
            }
            Additional provider-specific metrics can be included.
        """
        pass
    
    @abstractmethod
    def calculate_cost(self, usage: Dict[str, Any]) -> Tuple[float, float]:
        """
        Calculate costs based on usage and provider's pricing model.
        
        Args:
            usage: Usage dictionary from extract_usage()
            
        Returns:
            Tuple of (input_cost, output_cost) in USD
        """
        pass
    
    # Optional helper methods that providers can override
    
    def validate_model(self) -> bool:
        """
        Validate that the model is available/accessible.
        Default implementation just checks supports_model().
        
        Returns:
            True if model is valid and ready to use
        """
        return self.supports_model(self.model_name)
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.
        
        Returns:
            Dictionary with model metadata (context length, capabilities, etc.)
        """
        return {
            "model_name": self.model_name,
            "provider": self.__class__.__name__
        }