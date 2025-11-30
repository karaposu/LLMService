#!/usr/bin/env python3
"""
Test script for Structured Outputs integration.
Tests the new structured output functionality with the Responses API.


python test_structured_outputs.py
"""

import os
import sys
import logging
from pydantic import BaseModel, Field
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llmservice.generation_engine import GenerationEngine
from llmservice.structured_schemas import (
    SemanticIsolation,
    EntitiesList,
    ChainOfThought,
    Summary,
    SentimentAnalysis
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_simple_extraction():
    """Test simple semantic isolation with structured output."""
    print("\n" + "="*60)
    print("TEST 1: Simple Semantic Isolation")
    print("="*60)
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    # Test data
    text = "The patient John Doe, age 45, presented with severe headache and fever lasting 3 days. Blood pressure was 140/90."
    
    # Use structured semantic isolation
    try:
        result = engine.semantic_isolation_v2(
            content=text,
            element="symptoms"
        )
        print(f"✅ Extracted symptoms: {result}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False
    
    return True


def test_entity_extraction():
    """Test entity extraction with structured output."""
    print("\n" + "="*60)
    print("TEST 2: Entity Extraction")
    print("="*60)
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    text = "Apple Inc. announced that Tim Cook will visit Paris next Monday to meet with Emmanuel Macron."
    
    try:
        entities = engine.extract_entities(text)
        print(f"✅ Extracted {len(entities)} entities:")
        for entity in entities:
            print(f"   - {entity['name']} ({entity['type']}): {entity['value']}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False
    
    return True


def test_custom_schema():
    """Test with custom Pydantic schema."""
    print("\n" + "="*60)
    print("TEST 3: Custom Schema Extraction")
    print("="*60)
    
    # Define custom schema
    class ProductReview(BaseModel):
        product_name: str = Field(description="Name of the product")
        rating: float = Field(ge=1, le=5, description="Rating from 1 to 5")
        pros: List[str] = Field(description="Positive aspects")
        cons: List[str] = Field(description="Negative aspects")
        recommendation: bool = Field(description="Whether reviewer recommends the product")
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    review_text = """
    I recently bought the Sony WH-1000XM5 headphones and I have mixed feelings.
    The sound quality is absolutely amazing - best I've ever heard. The noise
    cancellation is also top-notch, perfect for flights. However, they're quite
    expensive at $400 and the battery life could be better (only 30 hours).
    Overall, I'd give them 4 out of 5 stars and would recommend them if you
    can afford the price.
    """
    
    try:
        review = engine.generate_structured(
            prompt=review_text,
            schema=ProductReview,
            system="Extract review information from the text"
        )
        
        print(f"✅ Parsed review:")
        print(f"   Product: {review.product_name}")
        print(f"   Rating: {review.rating}/5")
        print(f"   Pros: {', '.join(review.pros)}")
        print(f"   Cons: {', '.join(review.cons)}")
        print(f"   Recommended: {'Yes' if review.recommendation else 'No'}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False
    
    return True


def test_chain_of_thought():
    """Test chain-of-thought reasoning with structured output."""
    print("\n" + "="*60)
    print("TEST 4: Chain of Thought Reasoning")
    print("="*60)
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    problem = "If a train travels 60 miles in 1.5 hours, what is its average speed in mph?"
    
    try:
        result = engine.process_with_schema(
            content=problem,
            schema=ChainOfThought,
            instructions="Solve this problem step by step"
        )
        
        print(f"✅ Solution with {len(result.steps)} steps:")
        for i, step in enumerate(result.steps, 1):
            print(f"   Step {i}: {step.explanation}")
            print(f"           → {step.output}")
        print(f"   Final Answer: {result.final_answer}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False
    
    return True


def test_sentiment_analysis():
    """Test sentiment analysis with structured output."""
    print("\n" + "="*60)
    print("TEST 5: Sentiment Analysis")
    print("="*60)
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    text = "The product quality exceeded my expectations! However, the shipping was a bit slow."
    
    try:
        result = engine.process_with_schema(
            content=text,
            schema=SentimentAnalysis,
            instructions="Analyze the sentiment of this text"
        )
        
        print(f"✅ Sentiment Analysis:")
        print(f"   Overall: {result.overall_sentiment}")
        print(f"   Scores: Positive={result.scores.positive:.2f}, "
              f"Negative={result.scores.negative:.2f}, "
              f"Neutral={result.scores.neutral:.2f}")
        if result.key_phrases:
            print(f"   Key phrases: {', '.join(result.key_phrases)}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False
    
    return True


def test_with_gpt5():
    """Test structured output with GPT-5 model."""
    print("\n" + "="*60)
    print("TEST 6: GPT-5 with Structured Output")
    print("="*60)
    
    # Skip if GPT-5 not available
    try:
        engine = GenerationEngine(model_name="gpt-5-mini")
    except Exception:
        print("⚠️  GPT-5 not available, skipping test")
        return True
    
    # Define a simple schema
    class SimpleAnswer(BaseModel):
        answer: str = Field(description="The answer")
        confidence: float = Field(ge=0, le=1, description="Confidence score")
    
    try:
        result = engine.generate_structured(
            prompt="What is the capital of France?",
            schema=SimpleAnswer,
            reasoning_effort="low"  # Use low reasoning for better format compliance
        )
        
        print(f"✅ GPT-5 Response:")
        print(f"   Answer: {result.answer}")
        print(f"   Confidence: {result.confidence:.2f}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False
    
    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("STRUCTURED OUTPUTS TEST SUITE")
    print("Testing the new Structured Outputs integration")
    print("="*60)
    
    tests = [
        ("Simple Extraction", test_simple_extraction),
        ("Entity Extraction", test_entity_extraction),
        ("Custom Schema", test_custom_schema),
        ("Chain of Thought", test_chain_of_thought),
        ("Sentiment Analysis", test_sentiment_analysis),
        ("GPT-5 Support", test_with_gpt5),
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
    print("TEST RESULTS")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Structured Outputs are working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check the output above for details.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)