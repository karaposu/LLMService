#!/usr/bin/env python3
"""
Comprehensive test for async functionality with structured outputs.
Tests that all async methods are working properly with the fixed async client.
"""

import asyncio
import os
import sys
from pydantic import BaseModel, Field
from typing import List, Optional
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llmservice.generation_engine import GenerationEngine
from llmservice.schemas import GenerationRequest
from llmservice import BaseLLMService


# Define test schemas
class SimpleResponse(BaseModel):
    answer: str = Field(description="The answer")
    confidence: float = Field(ge=0, le=1, description="Confidence score")


class MultiItem(BaseModel):
    items: List[str] = Field(description="List of items")
    count: int = Field(description="Number of items")


class TestAsyncService(BaseLLMService):
    """Service to test async operations."""
    
    def __init__(self):
        super().__init__(default_model_name="gpt-4o-mini")
        # Configure for async testing
        self.set_rate_limits(max_rpm=100, max_tpm=10000)
        self.set_concurrency(5)
    
    async def async_simple_question(self, question: str, request_id=None):
        """Ask a simple question asynchronously."""
        request = GenerationRequest(
            user_prompt=question,
            response_schema=SimpleResponse,
            model="gpt-4o-mini",
            request_id=request_id
        )
        
        result = await self.execute_generation_async(request)
        
        if result.success:
            data = json.loads(result.content)
            response = SimpleResponse(**data)
            return response
        else:
            raise Exception(f"Generation failed: {result.error_message}")
    
    async def async_list_items(self, prompt: str, request_id=None):
        """Generate a list asynchronously."""
        request = GenerationRequest(
            user_prompt=prompt,
            response_schema=MultiItem,
            model="gpt-4o-mini",
            request_id=request_id
        )
        
        result = await self.execute_generation_async(request)
        
        if result.success:
            data = json.loads(result.content)
            response = MultiItem(**data)
            return response
        else:
            raise Exception(f"Generation failed: {result.error_message}")


async def test_single_async_call():
    """Test a single async call."""
    print("\n" + "="*60)
    print("TEST 1: Single Async Call")
    print("="*60)
    
    service = TestAsyncService()
    
    try:
        result = await service.async_simple_question("What is 2+2?")
        print(f"✅ Answer: {result.answer}")
        print(f"   Confidence: {result.confidence:.2f}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def test_multiple_async_calls():
    """Test multiple concurrent async calls."""
    print("\n" + "="*60)
    print("TEST 2: Multiple Concurrent Async Calls")
    print("="*60)
    
    service = TestAsyncService()
    
    questions = [
        "What is the capital of France?",
        "What is 10 * 10?",
        "What color is the sky?",
        "How many days in a week?",
        "What is H2O?"
    ]
    
    try:
        # Launch all tasks concurrently
        tasks = [
            service.async_simple_question(q, request_id=i) 
            for i, q in enumerate(questions)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ Question {i}: {result}")
            else:
                print(f"✅ Question {i}: {result.answer} (confidence: {result.confidence:.2f})")
                success_count += 1
        
        print(f"\n   Success rate: {success_count}/{len(questions)}")
        return success_count == len(questions)
    
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def test_async_with_structured_lists():
    """Test async with structured list outputs."""
    print("\n" + "="*60)
    print("TEST 3: Async with Structured Lists")
    print("="*60)
    
    service = TestAsyncService()
    
    prompts = [
        "List 3 colors",
        "List 3 animals",
        "List 3 countries"
    ]
    
    try:
        tasks = [
            service.async_list_items(p, request_id=i)
            for i, p in enumerate(prompts)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ Prompt {i}: {result}")
            else:
                print(f"✅ Prompt {i}: {result.count} items - {', '.join(result.items)}")
                success_count += 1
        
        return success_count == len(prompts)
    
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def test_async_rate_limiting():
    """Test that rate limiting works with async."""
    print("\n" + "="*60)
    print("TEST 4: Async Rate Limiting")
    print("="*60)
    
    service = TestAsyncService()
    # Set very low rate limits to test
    service.set_rate_limits(max_rpm=6, max_tpm=1000)  # Only 6 per minute = 1 per 10 seconds
    
    print("Testing rate limiting with 3 rapid requests...")
    print("(Should complete without errors, but may be throttled)")
    
    try:
        import time
        start_time = time.time()
        
        tasks = [
            service.async_simple_question(f"What is {i}+{i}?", request_id=i)
            for i in range(3)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        
        print(f"✅ Completed {success_count}/3 requests in {elapsed:.2f}s")
        print(f"   Rate limiting is {'working' if elapsed > 0.5 else 'may not be enforced'}")
        
        return success_count == 3
    
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def test_direct_engine_async():
    """Test async directly with GenerationEngine."""
    print("\n" + "="*60)
    print("TEST 5: Direct GenerationEngine Async")
    print("="*60)
    
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    request = GenerationRequest(
        user_prompt="What is the meaning of life?",
        response_schema=SimpleResponse,
        model="gpt-4o-mini"
    )
    
    try:
        result = await engine.generate_output_async(request)
        
        if result.success:
            data = json.loads(result.content)
            response = SimpleResponse(**data)
            print(f"✅ Answer: {response.answer}")
            print(f"   Confidence: {response.confidence:.2f}")
            return True
        else:
            print(f"❌ Failed: {result.error_message}")
            return False
    
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def main():
    """Run all async tests."""
    print("\n" + "="*60)
    print("COMPREHENSIVE ASYNC TEST SUITE")
    print("Testing all async functionality with structured outputs")
    print("="*60)
    
    tests = [
        ("Single Async Call", test_single_async_call),
        ("Multiple Concurrent Calls", test_multiple_async_calls),
        ("Structured Lists", test_async_with_structured_lists),
        ("Rate Limiting", test_async_rate_limiting),
        ("Direct Engine Async", test_direct_engine_async),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if await test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print("ASYNC TEST RESULTS")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 All async operations are working correctly!")
        print("   The async client fix resolved all issues.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check the output above.")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)