#!/usr/bin/env python3
"""
Test if low reasoning effort fixes pipeline issues with GPT-5.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from llmservice.generation_engine import GenerationEngine
from llmservice.schemas import GenerationRequest

def test_pipeline_with_low_reasoning():
    engine = GenerationEngine(model_name='gpt-5-mini')
    
    print("\n" + "="*60)
    print("TESTING GPT-5-MINI PIPELINE WITH LOW REASONING")
    print("="*60)
    
    # Test 1: Semantic Isolation with LOW reasoning
    print("\n--- Test 1: Semantic Isolation (LOW reasoning) ---")
    request1 = GenerationRequest(
        user_prompt='The patient shows symptoms of severe headache and nausea. The diagnosis is migraine.',
        pipeline_config=[
            {
                'type': 'SemanticIsolation',
                'params': {
                    'semantic_element_for_extraction': 'symptoms only, as a simple list'
                }
            }
        ]
    )
    
    # Add low reasoning effort
    request1.reasoning_effort = "low"
    request1.verbosity = "low"
    
    result1 = engine.generate_output(request1)
    print(f"Success: {result1.success}")
    if result1.success:
        print(f"Extracted: {result1.content}")
        if result1.usage:
            print(f"Reasoning tokens: {result1.usage.get('reasoning_tokens', 0)}")
    else:
        print(f"Error: {result1.error_message}")
    
    # Test 2: JSON extraction with LOW reasoning
    print("\n--- Test 2: JSON Pipeline (LOW reasoning) ---")
    request2 = GenerationRequest(
        user_prompt='Return exactly this JSON: {"status": "active", "value": 42}',
        system_prompt='Return ONLY the requested JSON, no other text.',
        pipeline_config=[
            {'type': 'ConvertToDict', 'params': {}},
            {'type': 'ExtractValue', 'params': {'key': 'value'}}
        ]
    )
    
    # Add low reasoning effort  
    request2.reasoning_effort = "low"
    request2.verbosity = "low"
    
    result2 = engine.generate_output(request2)
    print(f"Success: {result2.success}")
    if result2.success:
        print(f"Extracted value: {result2.content}")
        if result2.usage:
            print(f"Reasoning tokens: {result2.usage.get('reasoning_tokens', 0)}")
    else:
        print(f"Error: {result2.error_message}")
    
    # Compare with MEDIUM reasoning (default)
    print("\n--- Test 3: Same JSON Pipeline (MEDIUM reasoning - default) ---")
    request3 = GenerationRequest(
        user_prompt='Return exactly this JSON: {"status": "active", "value": 42}',
        system_prompt='Return ONLY the requested JSON, no other text.',
        pipeline_config=[
            {'type': 'ConvertToDict', 'params': {}},
            {'type': 'ExtractValue', 'params': {'key': 'value'}}
        ]
    )
    
    # Don't set reasoning_effort (will use default "medium")
    
    result3 = engine.generate_output(request3)
    print(f"Success: {result3.success}")
    if result3.success:
        print(f"Extracted value: {result3.content}")
        if result3.usage:
            print(f"Reasoning tokens: {result3.usage.get('reasoning_tokens', 0)}")
    else:
        print(f"Error: {result3.error_message}")
    
    print("\n" + "="*60)
    print("SUMMARY:")
    print("- LOW reasoning should use fewer reasoning tokens")
    print("- LOW reasoning should follow formatting instructions better")
    print("- Use LOW for pipeline operations requiring strict formats")
    print("="*60)

if __name__ == "__main__":
    test_pipeline_with_low_reasoning()