"""
MyLLMService - Capital Finder Service Implementation

Demonstrates the new structured output features replacing the old pipeline system.
Uses Pydantic schemas for guaranteed format compliance.
"""

from typing import Optional
from pydantic import BaseModel, Field

from llmservice import BaseLLMService, GenerationRequest, GenerationResult


# Define structured output schemas
class CapitalOnly(BaseModel):
    """Schema for extracting just the capital name"""
    capital: str = Field(description="The name of the capital city")


class CountryInfo(BaseModel):
    """Schema for detailed country information"""
    country: str = Field(description="Country name")
    capital: str = Field(description="Capital city name")
    population: Optional[int] = Field(default=None, description="Population of the capital")
    language: Optional[str] = Field(default=None, description="Official language")


class MyLLMService(BaseLLMService):
    """Service for finding country capitals using modern LLMService features"""

    def __init__(self):
        """Initialize with sensible defaults"""
        super().__init__(
            default_model_name="gpt-4o-mini",
            max_rpm=30,  # Rate limit: 30 requests per minute
            max_tpm=10000,  # Token limit: 10,000 tokens per minute
            max_concurrent_requests=5
        )

    def ask_llm_to_tell_capital(self, country: str) -> GenerationResult:
        """
        Get full response about a country's capital.
        This uses basic generation without structured output.
        """
        prompt = f"What is the capital of {country}? Provide a brief description."

        generation_request = GenerationRequest(
            user_prompt=prompt,
            system_prompt="You are a helpful geography assistant.",
            model="gpt-4o-mini",
            operation_name="full_capital_response"
        )

        return self.execute_generation(generation_request)

    def get_capital_only(self, country: str) -> Optional[str]:
        """
        Extract ONLY the capital name using structured output.
        This replaces the old SemanticIsolation pipeline.

        Old way (deprecated):
            pipeline_config = [{
                'type': 'SemanticIsolation',
                'params': {'semantic_element_for_extraction': 'just the capital'}
            }]

        New way: Use structured output with Pydantic schema via GenerationRequest
        """
        import json

        # Use GenerationRequest to get proper tracking
        request = GenerationRequest(
            user_prompt=f"What is the capital of {country}?",
            system_prompt="Return only the capital city name, nothing else.",
            response_schema=CapitalOnly,
            model="gpt-4o-mini",
            operation_name="get_capital_only"
        )

        result = self.execute_generation(request)

        if result.success:
            try:
                data = json.loads(result.content)
                capital = CapitalOnly(**data)
                return capital.capital
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing capital: {e}")
                return None
        else:
            print(f"Error extracting capital: {result.error_message}")
            return None

    def get_capital_info(self, country: str) -> Optional[CountryInfo]:
        """
        Get detailed structured information about a country.
        Demonstrates complex structured output with optional fields.
        """
        import json

        # Use GenerationRequest for proper tracking and metrics
        request = GenerationRequest(
            user_prompt=f"Provide information about {country}",
            system_prompt="Extract country information including capital, population of the capital city (if known), and official language.",
            response_schema=CountryInfo,
            model="gpt-4o-mini",
            operation_name="get_capital_info"
        )
    
        result = self.execute_generation(request)

        if result.success:
            try:
                data = json.loads(result.content)
                return CountryInfo(**data)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing country info: {e}")
                return None
        else:
            print(f"Error getting country info: {result.error_message}")
            return None

    def get_usage_stats(self):
        """Get usage statistics for the session"""
        if hasattr(self, 'usage_stats'):
            return self.usage_stats.operation_usage
        return {}


# Alternative implementation using the request-based approach
class AlternativeService(BaseLLMService):
    """
    Alternative implementation showing how to use structured outputs
    through GenerationRequest directly.
    """

    def __init__(self):
        super().__init__(default_model_name="gpt-4o-mini")

    def get_capital_with_request(self, country: str) -> Optional[str]:
        """
        Get capital using GenerationRequest with response_schema.
        This approach gives you more control over the request.
        """
        import json

        request = GenerationRequest(
            user_prompt=f"What is the capital of {country}?",
            system_prompt="Return only the capital name.",
            response_schema=CapitalOnly,  # Specify schema directly
            model="gpt-4o-mini",
            operation_name="capital_extraction"
        )

        result = self.execute_generation(request)

        if result.success:
            try:
                # Parse the JSON response
                data = json.loads(result.content)
                capital_obj = CapitalOnly(**data)
                return capital_obj.capital
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing response: {e}")
                return None
        else:
            print(f"Generation failed: {result.error_message}")
            return None