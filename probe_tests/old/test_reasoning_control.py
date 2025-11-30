#!/usr/bin/env python3
"""
Test reasoning control for GPT-5 models.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from llmservice.generation_engine import GenerationEngine
from llmservice.schemas import GenerationRequest

def test_reasoning_levels():
    engine = GenerationEngine(model_name='gpt-5-mini')
    
    print("\n" + "="*60)
    print("TESTING REASONING CONTROL WITH GPT-5-MINI")
    print("="*60)
    
    prompt = 'Return only this JSON, nothing else: {"answer": "blue"}'
    
    # Test different reasoning efforts
    for effort in ["low", "medium", "high"]:
        print(f"\n--- Testing with reasoning_effort='{effort}' ---")
        
        request = GenerationRequest(
            user_prompt=prompt,
            system_prompt="Return ONLY the requested JSON. No explanations.",
            request_id=f"test_{effort}"
        )
        
        # Add reasoning_effort attribute manually (since schema doesn't have it yet)
        request.reasoning_effort = effort
        
        result = engine.generate_output(request)
        
        if result.success:
            print(f"Response: {result.content}")
            if result.usage:
                print(f"Reasoning tokens: {result.usage.get('reasoning_tokens', 0)}")
                print(f"Output tokens: {result.usage.get('output_tokens', 0)}")
        else:
            print(f"Error: {result.error_message}")
    
    # Test if we can disable reasoning entirely
    print(f"\n--- Testing WITHOUT reasoning (if supported) ---")
    
    request_no_reasoning = GenerationRequest(
        user_prompt=prompt,
        system_prompt="Return ONLY the requested JSON. No explanations.",
        request_id="test_no_reasoning"
    )
    
    # Try not setting reasoning_effort at all
    result_no_reasoning = engine.generate_output(request_no_reasoning)
    
    if result_no_reasoning.success:
        print(f"Response: {result_no_reasoning.content}")
        if result_no_reasoning.usage:
            print(f"Reasoning tokens: {result_no_reasoning.usage.get('reasoning_tokens', 0)}")
            print(f"Output tokens: {result_no_reasoning.usage.get('output_tokens', 0)}")

if __name__ == "__main__":
    test_reasoning_levels()