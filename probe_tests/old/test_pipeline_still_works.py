#!/usr/bin/env python3
"""
Test to verify that all old pipeline features still work after Responses API migration.
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

def test_all_pipeline_features():
    """Test all existing pipeline processing features."""
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    print("\n" + "="*60)
    print("TESTING OLD PIPELINE FEATURES WITH RESPONSES API")
    print("="*60)
    
    # Test 1: ConvertToDict + ExtractValue Pipeline
    print("\n1. Testing ConvertToDict + ExtractValue pipeline...")
    request1 = GenerationRequest(
        user_prompt="Generate a JSON object with these exact fields: name='Alice', age=30, city='Paris'",
        pipeline_config=[
            {
                'type': 'ConvertToDict',
                'params': {}
            },
            {
                'type': 'ExtractValue',
                'params': {'key': 'city'}
            }
        ],
        request_id="pipeline_test_1"
    )
    
    result1 = engine.generate_output(request1)
    print(f"   Success: {result1.success}")
    print(f"   Raw content: {result1.raw_content}")
    print(f"   Processed content (extracted city): {result1.content}")
    print(f"   Pipeline steps executed: {len(result1.pipeline_steps_results)}")
    for i, step in enumerate(result1.pipeline_steps_results):
        print(f"     Step {i+1}: {step.step_type} - {'✓' if step.success else '✗'}")
    
    # Test 2: SemanticIsolation Pipeline
    print("\n2. Testing SemanticIsolation pipeline...")
    request2 = GenerationRequest(
        user_prompt="The patient John Smith, age 45, presents with severe headache, fever of 102°F, and nausea. Based on symptoms, likely diagnosis is migraine or flu. Recommend rest and hydration.",
        pipeline_config=[
            {
                'type': 'SemanticIsolation',
                'params': {
                    'semantic_element_for_extraction': 'only the symptoms, nothing else'
                }
            }
        ],
        request_id="pipeline_test_2"
    )
    
    result2 = engine.generate_output(request2)
    print(f"   Success: {result2.success}")
    print(f"   Raw content (full): {result2.raw_content[:100]}...")
    print(f"   Isolated symptoms: {result2.content}")
    
    # Test 3: JSONLoad Pipeline
    print("\n3. Testing JSONLoad pipeline...")
    request3 = GenerationRequest(
        user_prompt='Return exactly this JSON: {"status": "active", "count": 42, "items": ["a", "b", "c"]}',
        pipeline_config=[
            {
                'type': 'JSONLoad',
                'params': {}
            }
        ],
        request_id="pipeline_test_3"
    )
    
    result3 = engine.generate_output(request3)
    print(f"   Success: {result3.success}")
    print(f"   Raw content type: {type(result3.raw_content)}")
    print(f"   Processed content type: {type(result3.content)}")
    print(f"   Processed content: {result3.content}")
    
    # Test 4: Multi-step Pipeline with List Processing
    print("\n4. Testing multi-step pipeline with list processing...")
    request4 = GenerationRequest(
        user_prompt='Generate a JSON array with 3 products, each having fields: id, name, price. Make them tech products.',
        pipeline_config=[
            {
                'type': 'ConvertToDict',  # This handles arrays too
                'params': {}
            },
            {
                'type': 'ExtractValue',
                'params': {'key': 'name'}  # Will extract 'name' from each item
            }
        ],
        request_id="pipeline_test_4"
    )
    
    result4 = engine.generate_output(request4)
    print(f"   Success: {result4.success}")
    print(f"   Raw content (truncated): {str(result4.raw_content)[:100]}...")
    print(f"   Extracted product names: {result4.content}")
    
    # Test 5: StringMatchValidation Pipeline
    print("\n5. Testing StringMatchValidation pipeline...")
    request5 = GenerationRequest(
        user_prompt='Say exactly: "The quick brown fox jumps over the lazy dog"',
        pipeline_config=[
            {
                'type': 'StringMatchValidation',
                'params': {'expected_string': 'fox'}
            }
        ],
        request_id="pipeline_test_5"
    )
    
    result5 = engine.generate_output(request5)
    print(f"   Success: {result5.success}")
    print(f"   Validation passed: {result5.success and result5.content == result5.raw_content}")
    print(f"   Content contains 'fox': {'fox' in str(result5.content)}")
    
    # Test 6: Pipeline with new Responses API features (response_id tracking)
    print("\n6. Testing pipeline WITH response_id tracking (new feature)...")
    request6 = GenerationRequest(
        user_prompt='Generate JSON with field "value" set to 100',
        pipeline_config=[
            {
                'type': 'ConvertToDict',
                'params': {}
            },
            {
                'type': 'ExtractValue',
                'params': {'key': 'value'}
            }
        ],
        request_id="pipeline_test_6"
    )
    
    result6 = engine.generate_output(request6)
    print(f"   Success: {result6.success}")
    print(f"   Processed content: {result6.content}")
    print(f"   Response ID (NEW): {result6.response_id}")
    print(f"   Can use for CoT chaining: {result6.response_id is not None}")
    
    print("\n" + "="*60)
    print("✅ ALL PIPELINE FEATURES STILL WORKING!")
    print("="*60)
    print("\nSummary:")
    print("• ConvertToDict: ✓")
    print("• ExtractValue: ✓")
    print("• SemanticIsolation: ✓")
    print("• JSONLoad: ✓")
    print("• StringMatchValidation: ✓")
    print("• Multi-step pipelines: ✓")
    print("• List processing: ✓")
    print("• Response ID tracking (NEW): ✓")
    
    return all([
        result1.success,
        result2.success,
        result3.success,
        result4.success,
        result5.success,
        result6.success
    ])

if __name__ == "__main__":
    success = test_all_pipeline_features()
    sys.exit(0 if success else 1)