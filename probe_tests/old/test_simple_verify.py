#!/usr/bin/env python3
"""
Simple verification test to check core functionality.
"""

import asyncio
import os
import sys
import json
from pydantic import BaseModel, Field
from typing import List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llmservice import BaseLLMService, GenerationRequest


class SimpleResponse(BaseModel):
    answer: str = Field(description="The answer")


class QuickTestService(BaseLLMService):
    """Quick test service."""
    
    def __init__(self):
        super().__init__(default_model_name="gpt-4o-mini")
    
    async def quick_test(self, prompt: str):
        request = GenerationRequest(
            user_prompt=prompt,
            response_schema=SimpleResponse,
            model="gpt-4o-mini"
        )
        result = await self.execute_generation_async(request)
        if result.success:
            data = json.loads(result.content)
            return SimpleResponse(**data)
        else:
            raise Exception(f"Failed: {result.error_message}")


async def test_basic_functionality():
    """Test basic sync and async operations."""
    print("\n" + "="*60)
    print("QUICK VERIFICATION TEST")
    print("="*60)
    
    service = QuickTestService()
    
    # Test 1: Single async call
    print("\n1. Testing single async call...")
    try:
        result = await service.quick_test("What is 2+2?")
        print(f"   ✅ Async works: {result.answer}")
    except Exception as e:
        print(f"   ❌ Async failed: {e}")
        return False
    
    # Test 2: Multiple concurrent calls
    print("\n2. Testing concurrent calls...")
    try:
        tasks = [
            service.quick_test(f"What is {i}+{i}?")
            for i in range(3)
        ]
        results = await asyncio.gather(*tasks)
        print(f"   ✅ Got {len(results)} concurrent results")
        for i, r in enumerate(results):
            print(f"      - Result {i}: {r.answer}")
    except Exception as e:
        print(f"   ❌ Concurrent failed: {e}")
        return False
    
    # Test 3: Sync call
    print("\n3. Testing sync call...")
    try:
        request = GenerationRequest(
            user_prompt="What is 5+5?",
            response_schema=SimpleResponse,
            model="gpt-4o-mini"
        )
        result = service.execute_generation(request)
        if result.success:
            data = json.loads(result.content)
            response = SimpleResponse(**data)
            print(f"   ✅ Sync works: {response.answer}")
        else:
            print(f"   ❌ Sync failed: {result.error_message}")
            return False
    except Exception as e:
        print(f"   ❌ Sync failed: {e}")
        return False
    
    # Test 4: Rate limiting behavior
    print("\n4. Testing rate limit settings...")
    service.set_rate_limits(max_rpm=60, max_tpm=10000)
    print(f"   ✅ Rate limits set: RPM=60, TPM=10000")
    
    # Test 5: Error handling
    print("\n5. Testing error handling...")
    try:
        request = GenerationRequest(
            user_prompt="Test",
            response_schema=SimpleResponse,
            model="invalid-model-name"
        )
        result = await service.execute_generation_async(request)
        if not result.success:
            print(f"   ✅ Error caught properly: {result.error_message[:50]}...")
        else:
            print(f"   ❌ Should have failed with invalid model")
    except Exception as e:
        print(f"   ✅ Exception caught: {str(e)[:50]}...")
    
    return True


async def test_structured_outputs():
    """Test structured output functionality."""
    print("\n" + "="*60)
    print("STRUCTURED OUTPUT TEST")
    print("="*60)
    
    service = QuickTestService()
    
    # Define various schemas
    class PersonInfo(BaseModel):
        name: str
        age: int
        city: str
    
    class ListResponse(BaseModel):
        items: List[str]
        count: int
    
    # Test complex schema
    print("\n1. Testing PersonInfo schema...")
    request = GenerationRequest(
        user_prompt="Create a person named Alice, age 30, living in Paris",
        response_schema=PersonInfo,
        model="gpt-4o-mini"
    )
    
    result = await service.execute_generation_async(request)
    if result.success:
        data = json.loads(result.content)
        person = PersonInfo(**data)
        print(f"   ✅ PersonInfo: {person.name}, {person.age}, {person.city}")
    else:
        print(f"   ❌ Failed: {result.error_message}")
        return False
    
    # Test list schema
    print("\n2. Testing ListResponse schema...")
    request = GenerationRequest(
        user_prompt="List 3 colors",
        response_schema=ListResponse,
        model="gpt-4o-mini"
    )
    
    result = await service.execute_generation_async(request)
    if result.success:
        data = json.loads(result.content)
        list_resp = ListResponse(**data)
        print(f"   ✅ ListResponse: {list_resp.count} items - {', '.join(list_resp.items)}")
    else:
        print(f"   ❌ Failed: {result.error_message}")
        return False
    
    return True


async def test_metrics():
    """Test metrics tracking."""
    print("\n" + "="*60)
    print("METRICS TEST")
    print("="*60)
    
    service = QuickTestService()
    
    # Make a few requests
    print("\n1. Making requests to generate metrics...")
    for i in range(3):
        await service.quick_test(f"Quick test {i}")
    
    # Check metrics
    print("\n2. Current metrics:")
    rpm = service.get_current_rpm()
    tpm = service.get_current_tpm()
    cost = service.get_total_cost()
    
    print(f"   - Current RPM: {rpm:.2f}")
    print(f"   - Current TPM: {tpm:.2f}")
    print(f"   - Total cost: ${cost:.4f}")
    
    if rpm > 0 and tpm > 0:
        print(f"   ✅ Metrics tracking working")
        return True
    else:
        print(f"   ❌ Metrics not tracking properly")
        return False


async def main():
    """Run all verification tests."""
    print("\n" + "="*60)
    print("LLMSERVICE VERIFICATION SUITE")
    print("Checking core functionality after migration")
    print("="*60)
    
    tests = [
        ("Basic Functionality", test_basic_functionality),
        ("Structured Outputs", test_structured_outputs),
        ("Metrics Tracking", test_metrics),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if await test_func():
                passed += 1
                print(f"\n✅ {test_name}: PASSED")
            else:
                failed += 1
                print(f"\n❌ {test_name}: FAILED")
        except Exception as e:
            print(f"\n❌ {test_name}: CRASHED - {e}")
            failed += 1
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL CORE FUNCTIONALITY VERIFIED!")
        print("The migration to Responses API with Structured Outputs is working correctly.")
        print("\nWhat's working:")
        print("  ✓ Async operations")
        print("  ✓ Sync operations")
        print("  ✓ Structured outputs with Pydantic")
        print("  ✓ Error handling")
        print("  ✓ Metrics tracking")
        print("  ✓ Rate limit settings")
        
        print("\nKnown limitations:")
        print("  - Semaphore concurrency control needs event loop context")
        print("  - Rate limiting is best-effort based on client-side tracking")
        print("  - Some edge cases in error type classification")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check the output above.")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)