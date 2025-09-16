#!/usr/bin/env python3
"""
Test to confirm pipelines have been completely removed.
Only structured outputs should work now.
"""

import os
import sys
from pydantic import BaseModel, Field
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llmservice.generation_engine import GenerationEngine
from llmservice.schemas import GenerationRequest


def test_pipelines_removed():
    """Verify that pipeline_config is no longer accepted."""
    print("\n" + "="*60)
    print("TEST 1: Confirm Pipelines Are Removed")
    print("="*60)
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    # This should fail - pipeline_config no longer exists
    try:
        result = engine.generate_output(GenerationRequest(
            user_prompt="Test",
            pipeline_config=[{'type': 'SemanticIsolation'}]  # Should fail
        ))
        print("❌ FAILED: pipeline_config was accepted (should be removed)")
        return False
    except TypeError as e:
        if "pipeline_config" in str(e):
            print("✅ PASSED: pipeline_config rejected - pipelines removed!")
            return True
        else:
            print(f"❌ FAILED: Unexpected error: {e}")
            return False


def test_no_pipeline_methods():
    """Verify pipeline methods are removed."""
    print("\n" + "="*60)
    print("TEST 2: Confirm Pipeline Methods Are Removed")
    print("="*60)
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    # Check that pipeline methods don't exist
    removed_methods = [
        'execute_pipeline',
        'process_semanticisolation', 
        'process_converttodict',
        'process_extractvalue',
        'process_stringmatchvalidation',
        'process_jsonload',
        '_migrate_pipeline_to_schema',
        '_suggest_schema_for_pipeline'
    ]
    
    all_removed = True
    for method in removed_methods:
        if hasattr(engine, method):
            print(f"❌ Method still exists: {method}")
            all_removed = False
        else:
            print(f"✅ Removed: {method}")
    
    return all_removed


def test_structured_outputs_work():
    """Verify structured outputs still work correctly."""
    print("\n" + "="*60)
    print("TEST 3: Structured Outputs Still Work")
    print("="*60)
    
    class TestSchema(BaseModel):
        message: str = Field(description="A test message")
        status: str = Field(description="Status (success/failure)")
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    try:
        result = engine.generate_output(GenerationRequest(
            user_prompt="Return a success message",
            response_schema=TestSchema
        ))
        
        if result.success:
            import json
            data = json.loads(result.content)
            test_obj = TestSchema(**data)
            print(f"✅ Structured output works: {test_obj.message} ({test_obj.status})")
            return True
        else:
            print(f"❌ Generation failed: {result.error_message}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_clean_imports():
    """Verify no pipeline-related imports remain."""
    print("\n" + "="*60)
    print("TEST 4: Clean Imports")
    print("="*60)
    
    # Check that String2Dict is not imported
    import llmservice.generation_engine as ge_module
    
    checks = {
        'String2Dict': hasattr(ge_module, 'String2Dict'),
        'PipelineStepResult imported': 'PipelineStepResult' in dir(ge_module),
    }
    
    all_clean = True
    for check, exists in checks.items():
        if exists:
            print(f"❌ Still present: {check}")
            all_clean = False
        else:
            print(f"✅ Removed: {check}")
    
    return all_clean


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PIPELINE COMPLETE REMOVAL TEST")
    print("Confirming pipelines are completely removed")
    print("="*60)
    
    tests = [
        ("Pipelines Removed", test_pipelines_removed),
        ("Pipeline Methods Removed", test_no_pipeline_methods),
        ("Structured Outputs Work", test_structured_outputs_work),
        ("Clean Imports", test_clean_imports),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 SUCCESS! Pipelines have been completely removed.")
        print("   Only structured outputs remain - clean and reliable!")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check the output above.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)