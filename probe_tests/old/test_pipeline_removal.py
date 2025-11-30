#!/usr/bin/env python3
"""
Test script demonstrating pipeline removal and structured output replacement.
Shows deprecation warnings and auto-migration.
"""

import os
import sys
import warnings
from pydantic import BaseModel, Field
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llmservice.generation_engine import GenerationEngine
from llmservice.schemas import GenerationRequest

# Enable deprecation warnings
warnings.simplefilter('always', DeprecationWarning)

def test_old_pipeline_with_deprecation():
    """Test that old pipeline code shows deprecation warnings."""
    print("\n" + "="*60)
    print("TEST 1: Old Pipeline Approach (Deprecated)")
    print("="*60)
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    # This will trigger deprecation warning
    print("\n⚠️  Using deprecated pipeline approach:")
    result = engine.generate_output(GenerationRequest(
        user_prompt="The patient has severe headache and fever. Extract the symptoms.",
        pipeline_config=[
            {'type': 'SemanticIsolation', 
             'params': {'semantic_element_for_extraction': 'symptoms'}},
            {'type': 'ConvertToDict', 'params': {}},
            {'type': 'ExtractValue', 'params': {'key': 'answer'}}
        ]
    ))
    
    if result.success:
        print(f"Result (with deprecation): {result.content}")
    else:
        print(f"Failed: {result.error_message}")

def test_auto_migration():
    """Test automatic migration from pipeline to structured output."""
    print("\n" + "="*60)
    print("TEST 2: Automatic Migration")
    print("="*60)
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    print("\n🔄 Auto-migrating SemanticIsolation pipeline to structured output:")
    
    # This will auto-migrate to SemanticIsolation schema
    result = engine.generate_output(GenerationRequest(
        user_prompt="The patient has severe headache and fever. Extract the symptoms.",
        pipeline_config=[
            {'type': 'SemanticIsolation', 
             'params': {'semantic_element_for_extraction': 'symptoms'}}
        ]
    ))
    
    if result.success:
        print(f"✅ Auto-migrated result: {result.content}")

def test_new_structured_approach():
    """Test the new recommended structured output approach."""
    print("\n" + "="*60)
    print("TEST 3: New Structured Output Approach (Recommended)")
    print("="*60)
    
    # Define custom schema
    class SymptomExtraction(BaseModel):
        symptoms: List[str] = Field(description="List of symptoms")
        severity: Optional[str] = Field(default=None, description="Overall severity")
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    print("\n✅ Using structured output (no warnings):")
    result = engine.generate_output(GenerationRequest(
        user_prompt="The patient has severe headache and fever.",
        system_prompt="Extract the symptoms from the medical text",
        response_schema=SymptomExtraction
    ))
    
    if result.success:
        import json
        data = json.loads(result.content)
        symptoms = SymptomExtraction(**data)
        print(f"Symptoms: {', '.join(symptoms.symptoms)}")
        if symptoms.severity:
            print(f"Severity: {symptoms.severity}")

def compare_approaches():
    """Compare old pipeline vs new structured output."""
    print("\n" + "="*60)
    print("COMPARISON: Pipeline vs Structured Output")
    print("="*60)
    
    text = "John Doe, age 45, diagnosed with diabetes and hypertension. Takes metformin and lisinopril."
    
    print("\n📝 Input text:")
    print(f"   {text}")
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    # Old pipeline approach
    print("\n❌ OLD WAY (Pipeline) - Multiple failure points:")
    print("   pipeline_config=[")
    print("       {'type': 'SemanticIsolation', ...},  # Can fail")
    print("       {'type': 'ConvertToDict', ...},      # Can fail")
    print("       {'type': 'ExtractValue', ...}        # Can fail")
    print("   ]")
    
    # New structured approach
    print("\n✅ NEW WAY (Structured Output) - Zero failures:")
    
    class MedicalInfo(BaseModel):
        patient_name: str
        age: int
        conditions: List[str]
        medications: List[str]
    
    result = engine.generate_output(GenerationRequest(
        user_prompt=text,
        response_schema=MedicalInfo
    ))
    
    if result.success:
        import json
        data = json.loads(result.content)
        info = MedicalInfo(**data)
        print(f"   Patient: {info.patient_name}, Age: {info.age}")
        print(f"   Conditions: {', '.join(info.conditions)}")
        print(f"   Medications: {', '.join(info.medications)}")
        print("\n   ✨ Direct access, type-safe, no parsing errors!")

def show_migration_guide():
    """Display migration guide for common patterns."""
    print("\n" + "="*60)
    print("MIGRATION GUIDE")
    print("="*60)
    
    print("\n📚 Common Pipeline Replacements:\n")
    
    print("1. SemanticIsolation -> Custom Schema:")
    print("   OLD: pipeline_config=[{'type': 'SemanticIsolation', ...}]")
    print("   NEW: response_schema=SemanticIsolation")
    print("")
    
    print("2. ConvertToDict + ExtractValue -> Direct Schema:")
    print("   OLD: pipeline_config=[")
    print("        {'type': 'ConvertToDict'},")
    print("        {'type': 'ExtractValue', 'params': {'key': 'data'}}")
    print("   ]")
    print("   NEW: response_schema=MyDataSchema  # With 'data' field")
    print("")
    
    print("3. JSONLoad -> Structured Schema:")
    print("   OLD: pipeline_config=[{'type': 'JSONLoad'}]")
    print("   NEW: response_schema=StructuredData")
    print("")
    
    print("4. StringMatchValidation -> Pydantic Validators:")
    print("   OLD: pipeline_config=[")
    print("        {'type': 'StringMatchValidation', 'params': {'expected': 'yes'}}")
    print("   ]")
    print("   NEW: Use Literal['yes', 'no'] in your schema")

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PIPELINE REMOVAL DEMONSTRATION")
    print("Showing deprecation warnings and migration path")
    print("="*60)
    
    # Run tests
    test_old_pipeline_with_deprecation()
    test_auto_migration()
    test_new_structured_approach()
    compare_approaches()
    show_migration_guide()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("\n🎯 Key Points:")
    print("1. Pipelines are deprecated and will be removed in v3.0")
    print("2. Auto-migration helps transition existing code")
    print("3. Structured outputs are simpler and more reliable")
    print("4. Zero parsing errors with Pydantic schemas")
    print("\n📖 See devdocs/pipeline_migration_plan.md for full details")

if __name__ == "__main__":
    main()