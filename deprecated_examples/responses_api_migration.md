# Responses API Migration Examples

This document provides examples of how to use the new OpenAI Responses API features in LLMService after the migration.

## Overview of Changes

The Responses API replaces the Chat Completions API with several improvements:
- 40-80% cost reduction through cache utilization
- Built-in Chain-of-Thought (CoT) support via `previous_response_id`
- Native tools (web_search, file_search, code_interpreter)
- Reasoning tokens tracked separately
- Stateful context with `store: true`
- 3% performance improvement on benchmarks

## Basic Usage

### Simple Text Generation

```python
from llmservice.generation_engine import GenerationEngine
from llmservice.schemas import GenerationRequest

# Initialize the engine
engine = GenerationEngine(model_name="gpt-4o-mini")

# Create a request
request = GenerationRequest(
    user_prompt="Explain machine learning in one sentence.",
    system_prompt="You are a helpful AI assistant.",
    request_id="example_1"
)

# Generate response
result = engine.generate_output(request)

print(f"Response: {result.content}")
print(f"Response ID: {result.response_id}")  # New: for CoT chaining
print(f"Reasoning tokens: {result.usage.get('reasoning_tokens', 0)}")  # New: reasoning tracking
```

## Chain-of-Thought (CoT) Chaining

The Responses API allows you to chain responses together for coherent multi-turn reasoning:

```python
from llmservice.generation_engine import GenerationEngine
from llmservice.schemas import GenerationRequest

engine = GenerationEngine(model_name="gpt-4o-mini")

# First request in the chain
request1 = GenerationRequest(
    user_prompt="What are the main components of a neural network?",
    request_id="cot_1"
)

result1 = engine.generate_with_cot_chain(request1)
print(f"First response: {result1.content}")
print(f"Response ID: {result1.response_id}")

# Chain a follow-up question using the previous response ID
if result1.response_id:
    request2 = GenerationRequest(
        user_prompt="How does backpropagation work with these components?",
        request_id="cot_2"
    )
    
    # Pass the previous response_id to maintain context
    result2 = engine.generate_with_cot_chain(
        request2, 
        previous_response_id=result1.response_id
    )
    
    print(f"Chained response: {result2.content}")
    # The model remembers the context from the previous response
```

## Using Native Tools

The Responses API includes built-in tools that don't require function definitions:

```python
# Web Search Example
request = GenerationRequest(
    user_prompt="Search for the latest news about renewable energy and summarize the top 3 stories.",
    system_prompt="Use web search to find current information.",
    request_id="web_search_example"
)

result = engine.generate_output(request)
# The model will automatically use web_search tool if needed

# File Search Example (when available)
request = GenerationRequest(
    user_prompt="Find information about the company's Q3 earnings in the uploaded documents.",
    system_prompt="Search through the provided files for relevant information.",
    request_id="file_search_example"
)
```

## Reasoning Effort Control

For models that support it (like GPT-5 when available), you can control reasoning effort:

```python
from llmservice.schemas import GenerationRequest

# High reasoning effort for complex problems
request = GenerationRequest(
    user_prompt="Solve this optimization problem: minimize f(x,y) = x^2 + y^2 subject to x + y = 1",
    system_prompt="Show detailed mathematical reasoning.",
    request_id="math_problem"
)

# Note: Add reasoning_effort when schema is updated
# request.reasoning_effort = "high"  # Options: low, medium, high

result = engine.generate_output(request)

# Check reasoning token usage
if result.usage:
    print(f"Reasoning tokens: {result.usage.get('reasoning_tokens', 0)}")
    print(f"Reasoning cost: ${result.usage.get('reasoning_cost', 0):.6f}")
```

## Async Operations

The Responses API integration maintains full async support:

```python
import asyncio
from llmservice.generation_engine import GenerationEngine
from llmservice.schemas import GenerationRequest

async def async_example():
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    # Create multiple requests
    requests = [
        GenerationRequest(
            user_prompt=f"Task {i}: Generate a haiku about {topic}",
            request_id=f"async_{i}"
        )
        for i, topic in enumerate(["mountains", "oceans", "forests"])
    ]
    
    # Execute concurrently
    tasks = [engine.generate_output_async(req) for req in requests]
    results = await asyncio.gather(*tasks)
    
    for i, result in enumerate(results):
        print(f"Haiku {i+1}: {result.content}")
    
    # Async CoT chaining
    if results[0].response_id:
        follow_up = GenerationRequest(
            user_prompt="Now combine elements from all three haikus into one.",
            request_id="async_combined"
        )
        
        combined = await engine.generate_with_cot_chain_async(
            follow_up,
            previous_response_id=results[0].response_id
        )
        print(f"Combined: {combined.content}")

# Run the async example
asyncio.run(async_example())
```

## Cost Tracking with Reasoning Tokens

The new API tracks reasoning tokens separately:

```python
def analyze_costs(result):
    """Analyze costs including reasoning tokens."""
    if not result.usage:
        return
    
    usage = result.usage
    
    print("Token Usage Breakdown:")
    print(f"  Input tokens: {usage.get('input_tokens', 0)}")
    print(f"  Output tokens: {usage.get('output_tokens', 0)}")
    print(f"  Reasoning tokens: {usage.get('reasoning_tokens', 0)}")  # New
    
    print("\nCost Breakdown:")
    print(f"  Input cost: ${usage.get('input_cost', 0):.6f}")
    print(f"  Output cost: ${usage.get('output_cost', 0):.6f}")
    print(f"  Reasoning cost: ${usage.get('reasoning_cost', 0):.6f}")  # New
    print(f"  Total cost: ${usage.get('total_cost', 0):.6f}")
    
    # Cache savings (when applicable)
    cached = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
    if cached > 0:
        print(f"\n✨ Cache hit: {cached} tokens (cost savings!)")

# Use with any result
result = engine.generate_output(request)
analyze_costs(result)
```

## Pipeline Integration

The Responses API works seamlessly with existing pipelines:

```python
request = GenerationRequest(
    user_prompt="Generate a JSON object with patient data: name='John Doe', age=35, diagnosis='flu'",
    pipeline_config=[
        {
            'type': 'ConvertToDict',
            'params': {}
        },
        {
            'type': 'ExtractValue',
            'params': {'key': 'diagnosis'}
        }
    ],
    request_id="pipeline_example"
)

result = engine.generate_output(request)
print(f"Extracted diagnosis: {result.content}")  # Will output: "flu"
print(f"Response ID for chaining: {result.response_id}")
```

## Migration Checklist

When migrating your code to use the Responses API:

1. **No changes needed for basic usage** - The integration handles the API switch transparently
2. **Add response_id tracking** - Store `result.response_id` for CoT chaining
3. **Update cost monitoring** - Include reasoning tokens in your metrics
4. **Leverage CoT chaining** - Use `generate_with_cot_chain()` for multi-turn reasoning
5. **Remove function definitions for native tools** - Web search, file search, and code interpreter are built-in
6. **Monitor cache hits** - Check `cached_tokens` in usage details for cost savings

## Model Support

All OpenAI models now use the Responses API:
- `gpt-4o-mini` - Most cost-effective
- `gpt-4o` - Balanced performance
- `gpt-4o-audio-preview` - Multimodal with audio
- `o1`, `o1-pro` - Advanced reasoning (high reasoning token usage)
- `o3`, `o4-mini` - Latest models with enhanced capabilities

## Troubleshooting

### Response ID Not Available
```python
if result.response_id:
    # Chain next request
    pass
else:
    # Fallback to independent request
    print("Warning: Response ID not available, CoT chaining disabled")
```

### Reasoning Tokens Show Zero
- This is normal for models like `gpt-4o-mini`
- Reasoning tokens are primarily used by o1/o3 models
- The field is included for forward compatibility

### Cost Calculations
```python
# Costs are automatically calculated including reasoning tokens
print(f"Total cost: ${result.usage.get('total_cost', 0):.6f}")

# Breakdown available in usage dict:
# - input_cost
# - output_cost  
# - reasoning_cost (new)
# - total_cost (sum of all)
```

## Performance Tips

1. **Enable caching**: Responses are stored with `store: true` by default
2. **Use CoT chaining**: Maintains context without repeating information
3. **Batch similar requests**: The API can optimize repeated patterns
4. **Monitor cache hits**: Cached tokens significantly reduce costs
5. **Choose appropriate models**: Use `gpt-4o-mini` for simple tasks, reserve o1/o3 for complex reasoning

## Further Resources

- [OpenAI Responses API Documentation](https://docs.openai.com/responses-api)
- [Migration Guide](devdocs/refactor_plan.md)
- [Test Suite](test_responses_simple.py)