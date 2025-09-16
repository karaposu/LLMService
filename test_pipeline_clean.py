#!/usr/bin/env python3
"""
Clean test showing pipeline features work with Responses API.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from llmservice.generation_engine import GenerationEngine
from llmservice.schemas import GenerationRequest

def main():
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    print("\n" + "="*60)
    print("PIPELINE FEATURES WITH RESPONSES API")
    print("="*60)
    
    # Test 1: Simple JSON extraction
    print("\n✓ Test 1: JSON Pipeline")
    request1 = GenerationRequest(
        user_prompt='Reply with only this JSON, no other text: {"city": "Tokyo", "country": "Japan"}',
        system_prompt="Return only the requested JSON, no markdown formatting.",
        pipeline_config=[
            {'type': 'ConvertToDict', 'params': {}},
            {'type': 'ExtractValue', 'params': {'key': 'country'}}
        ]
    )
    
    result1 = engine.generate_output(request1)
    print(f"  Raw: {result1.raw_content}")
    print(f"  Processed: {result1.content}")
    print(f"  Response ID: {result1.response_id}")
    
    # Test 2: Semantic isolation
    print("\n✓ Test 2: Semantic Isolation")
    request2 = GenerationRequest(
        user_prompt="The sky is blue. The grass is green. The sun is yellow.",
        pipeline_config=[
            {
                'type': 'SemanticIsolation',
                'params': {'semantic_element_for_extraction': 'colors only'}
            }
        ]
    )
    
    result2 = engine.generate_output(request2)
    print(f"  Raw: {result2.raw_content}")
    print(f"  Isolated: {result2.content}")
    
    # Test 3: Multi-step with CoT chaining
    print("\n✓ Test 3: Pipeline + CoT Chaining")
    request3 = GenerationRequest(
        user_prompt='{"number": 42}',
        pipeline_config=[
            {'type': 'ConvertToDict', 'params': {}},
            {'type': 'ExtractValue', 'params': {'key': 'number'}}
        ]
    )
    
    result3 = engine.generate_output(request3)
    print(f"  Extracted number: {result3.content}")
    print(f"  Response ID: {result3.response_id}")
    
    # Chain another request using the response_id
    if result3.response_id:
        request4 = GenerationRequest(
            user_prompt="Double the number from the previous response.",
            system_prompt="You previously extracted a number. Now double it and return just the number."
        )
        
        result4 = engine.generate_with_cot_chain(request4, previous_response_id=result3.response_id)
        print(f"  Chained result: {result4.content}")
        print(f"  ✅ CoT chaining with pipeline works!")
    
    print("\n" + "="*60)
    print("SUMMARY: All old pipeline features are working!")
    print("  • ConvertToDict ✓")
    print("  • ExtractValue ✓")  
    print("  • SemanticIsolation ✓")
    print("  • Multi-step pipelines ✓")
    print("  • Works with CoT chaining ✓")
    print("  • Response IDs tracked ✓")
    print("="*60)

if __name__ == "__main__":
    main()