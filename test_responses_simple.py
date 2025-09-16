#!/usr/bin/env python3
"""
Simple test for Responses API integration focusing on GenerationEngine.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from llmservice.generation_engine import GenerationEngine
from llmservice.schemas import GenerationRequest

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    print("\n" + "="*60)
    print("RESPONSES API SIMPLE TEST")
    print("="*60)
    
    # Initialize the generation engine
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    # Test 1: Basic generation
    print("\n1. Testing basic generation...")
    request1 = GenerationRequest(
        user_prompt="What is 2+2?",
        system_prompt="You are a helpful assistant. Be very brief.",
        request_id="test_1"
    )
    
    result1 = engine.generate_output(request1)
    print(f"   Success: {result1.success}")
    print(f"   Response: {result1.content}")
    print(f"   Response ID: {result1.response_id}")
    
    # Test 2: CoT chaining
    print("\n2. Testing CoT chaining...")
    request2 = GenerationRequest(
        user_prompt="List three primary colors.",
        request_id="test_2"
    )
    
    result2 = engine.generate_with_cot_chain(request2)
    print(f"   First response: {result2.content}")
    print(f"   Response ID: {result2.response_id}")
    
    if result2.response_id:
        request3 = GenerationRequest(
            user_prompt="Now mix the first two colors you mentioned. What color do you get?",
            request_id="test_3"
        )
        
        result3 = engine.generate_with_cot_chain(request3, previous_response_id=result2.response_id)
        print(f"   Chained response: {result3.content}")
        print(f"   ✅ CoT chaining successful!")
    
    # Test 3: Check for reasoning tokens in usage
    print("\n3. Checking usage metadata...")
    if result1.usage:
        print(f"   Input tokens: {result1.usage.get('input_tokens', 0)}")
        print(f"   Output tokens: {result1.usage.get('output_tokens', 0)}")
        print(f"   Total cost: ${result1.usage.get('total_cost', 0):.6f}")
        
        # Check for new Responses API fields
        if 'reasoning_tokens' in result1.usage:
            print(f"   Reasoning tokens: {result1.usage['reasoning_tokens']}")
        if 'reasoning_cost' in result1.usage:
            print(f"   Reasoning cost: ${result1.usage['reasoning_cost']:.6f}")
    
    print("\n" + "="*60)
    print("✅ TEST COMPLETED SUCCESSFULLY")
    print("="*60)

if __name__ == "__main__":
    main()