# Introduction to LLMService Codebase

Welcome to the LLMService project! This document will help you understand how the codebase is architected, how data flows through the system, and the key design patterns that make this project maintainable and extensible.

## 🏗️ High-Level Architecture

Think of LLMService as a **smart pipeline** that sits between your application and various AI providers. It's built with a clean **layered architecture** where each layer has a specific job:

```
┌─────────────────────────────────────┐
│     Your Application Code           │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Service Orchestration Layer       │ ← Rate limiting, metrics, coordination
│      (BaseLLMService)               │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    Generation Engine Layer          │ ← Business logic, request processing
│     (GenerationEngine)              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      LLM Handler Layer              │ ← Provider selection, retry logic
│        (LLMHandler)                 │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Provider Layer                 │ ← API-specific implementations
│  (OpenAI, Claude, Ollama, etc.)    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    External AI Services             │
│  (GPT-4, Claude, Local Models)      │
└─────────────────────────────────────┘
```

## 🔄 Data Flow Paths

### The Journey of a Request

When you make a request to generate text, here's the path it takes:

1. **Entry Point** (`MyLLMService.ask_llm()`)
   - Your code creates a `GenerationRequest` with your prompt and configuration
   - This enters the service through `BaseLLMService.execute_generation()`

2. **Traffic Control** (`BaseLLMService`)
   - **RPM Gate**: "Are we sending too many requests per minute?"
   - **TPM Gate**: "Are we using too many tokens per minute?"
   - If limits are reached, the request waits intelligently

3. **Processing** (`GenerationEngine`)
   - Converts `GenerationRequest` → `LLMCallRequest` (normalization)
   - Adds metadata like trace IDs for tracking
   - Handles structured output schemas if specified

4. **Provider Selection** (`LLMHandler`)
   - Selects the right provider based on the model name
   - Implements retry logic with exponential backoff
   - Tracks timing for each attempt

5. **API Translation** (`Provider`)
   - Converts internal format to provider-specific format
   - Makes the actual HTTP call to the AI service
   - Extracts usage data and costs from response

6. **Response Journey Back**
   - Provider response → `InvokeResponseData` → `GenerationResult`
   - Each layer adds its own metadata (timings, costs, retries)
   - Final response includes both the AI output and rich telemetry

### Data Transformation Pipeline

```python
# What you write:
GenerationRequest(user_prompt="What's the capital of France?")
                    ↓
# Internal normalization:
LLMCallRequest(user_prompt="...", model_name="gpt-4o-mini")
                    ↓
# Provider-specific format:
{"model": "gpt-4o-mini", "input": "...", "instructions": None}
                    ↓
# AI Response:
Response(output_text="Paris", usage={...})
                    ↓
# Enriched result:
GenerationResult(
    content="Paris",
    usage={"tokens": 15, "cost": 0.0001},
    elapsed_time=0.8,
    trace_id="uuid-here"
)
```

## 🎯 Main Abstractions

### Core Abstractions You'll Work With

1. **`GenerationRequest`** - What you want from the AI
   - Supports text, images, audio
   - Can specify structured output schemas
   - Contains all configuration for the request

2. **`GenerationResult`** - What you get back
   - The AI's response (`content`)
   - Usage metrics and costs
   - Timing information
   - Success/failure status

3. **`BaseLLMService`** - Your main interface
   - Subclass this to create your service
   - Handles all the complex orchestration
   - Provides rate limiting and metrics automatically

4. **`BaseLLMProvider`** - How we talk to AI services
   - Each AI service has its own provider
   - Handles API-specific details
   - Easily extendable for new services

### Supporting Abstractions

- **`MetricsRecorder`** - Real-time metrics tracking
  - Thread-safe sliding window calculations
  - RPM/TPM/cost tracking
  - No external dependencies

- **`RpmGate` & `TpmGate`** - Rate limiting controllers
  - Smart waiting based on sliding windows
  - Coordinates multiple concurrent requests
  - Prevents API rate limit errors

- **`EventTimestamps`** - Detailed timing information
  - Tracks every stage of request processing
  - Helps identify performance bottlenecks
  - Useful for debugging and optimization

## 🎨 Design Patterns

### Strategy Pattern (Provider System)

The system uses the **Strategy Pattern** to support multiple AI providers:

```python
# Each provider is a strategy
class OpenAIProvider(BaseLLMProvider):
    def _invoke_impl(self, payload):
        # OpenAI-specific logic

class ClaudeProvider(BaseLLMProvider):
    def _invoke_impl(self, payload):
        # Claude-specific logic

# LLMHandler selects the right strategy
if model.startswith("gpt"):
    provider = OpenAIProvider()
elif model.startswith("claude"):
    provider = ClaudeProvider()
```

**Why this matters**: You can add new AI providers without changing any existing code.

### Template Method Pattern (Request Processing)

The request processing flow is a template with customizable steps:

```python
class BaseLLMService:
    def execute_generation(self, request):
        # This is the template
        self._check_rate_limits()      # Step 1
        result = self._process()        # Step 2
        self._update_metrics(result)   # Step 3
        return result

class MyLLMService(BaseLLMService):
    # Customize specific behaviors without changing the flow
```

**Why this matters**: Consistent behavior across all services while allowing customization.

### Facade Pattern (Generation Engine)

The `GenerationEngine` provides a simple interface to complex operations:

```python
# Complex operations hidden behind simple methods
engine.generate_output(request)  # Handles retries, providers, schemas, etc.
engine.process_with_schema(text, MySchema)  # Complex structured output
engine.extract_entities(text)  # Sophisticated NLP task
```

**Why this matters**: You don't need to understand the complexity to use the features.

### Observer Pattern (Metrics)

Components observe request lifecycle events:

```python
# When a request is sent:
metrics.mark_sent(request_id)  # MetricsRecorder observes

# When response arrives:
metrics.mark_rcv(request_id, tokens=50, cost=0.001)  # Updates multiple metrics

# Multiple observers can track the same events
usage_stats.update(response)  # Another observer
```

**Why this matters**: Metrics and telemetry are cleanly separated from business logic.

## 🔧 Extension Points

### Adding a New Provider

1. Create a class inheriting from `BaseLLMProvider`
2. Implement the required methods
3. Register it in the provider selection logic

```python
class MyCustomProvider(BaseLLMProvider):
    @classmethod
    def supports_model(cls, model_name: str) -> bool:
        return model_name.startswith("my-model")

    def convert_request(self, request):
        # Convert to your API format

    def _invoke_impl(self, payload):
        # Make your API call
```

### Creating a Custom Service

```python
class MyLLMService(BaseLLMService):
    def analyze_sentiment(self, text: str) -> str:
        request = GenerationRequest(
            user_prompt=f"Analyze sentiment: {text}",
            response_schema=SentimentSchema  # Force structured output
        )
        result = self.execute_generation(request)
        return result.content.sentiment  # Type-safe access
```

### 🎯 Structured Outputs - The Core Innovation

Structured Outputs are the **crown jewel** of the new LLMService architecture, replacing the old pipeline system with guaranteed type-safe responses. Here are **all the ways** to use them:

#### Method 1: Direct Schema in GenerationRequest (Most Flexible)

```python
from pydantic import BaseModel
import json

class ProductInfo(BaseModel):
    name: str
    price: float
    in_stock: bool

# Use schema directly in request
request = GenerationRequest(
    user_prompt="iPhone 15 Pro costs $999 and is available",
    response_schema=ProductInfo  # ← Guarantees structured output
)

result = service.execute_generation(request)

# Parse the JSON response
if result.success:
    data = json.loads(result.content)  # result.content is JSON string
    product = ProductInfo(**data)      # Create Pydantic model
    print(f"{product.name}: ${product.price}")  # Type-safe access
```

#### Method 2: Using process_with_schema() (Auto-Parsed)

```python
# Returns parsed Pydantic model directly - no JSON parsing needed!
product = engine.process_with_schema(
    content="iPhone 15 Pro costs $999 and is available",
    schema=ProductInfo,
    instructions="Extract product information"  # Optional system prompt
)

print(product.name)        # "iPhone 15 Pro" - Already parsed!
print(product.price)       # 999.0
print(product.in_stock)    # True
```

#### Method 3: Using generate_structured() (Simplified Alias)

```python
# Cleaner alias for process_with_schema
product = engine.generate_structured(
    prompt="iPhone 15 Pro costs $999 and is available",
    schema=ProductInfo,
    system="Extract product details"  # Optional
)

print(f"Product: {product.name}")  # Direct access, no parsing
```

#### Method 4: Built-in Extraction Methods

```python
# For common tasks - no schema definition needed!

# 1. Semantic Isolation (extract specific elements)
symptoms = engine.semantic_isolation_v2(
    content="Patient has fever, headache, and nausea for 3 days",
    element="symptoms"
)
print(symptoms)  # "fever, headache, and nausea"

# 2. Entity Extraction (NER)
entities = engine.extract_entities(
    text="Apple CEO Tim Cook will meet President Biden in Washington"
)
# Returns: [
#   {"name": "Apple", "type": "ORG", "value": "Technology company"},
#   {"name": "Tim Cook", "type": "PERSON", "value": "CEO of Apple"},
#   {"name": "President Biden", "type": "PERSON", "value": "US President"},
#   {"name": "Washington", "type": "LOC", "value": "US Capital"}
# ]
```

#### Method 5: In Service Classes (Best Practice)

```python
class MyLLMService(BaseLLMService):
    async def extract_product_async(self, description: str) -> ProductInfo:
        """Extract product info with automatic parsing."""
        request = GenerationRequest(
            user_prompt=description,
            response_schema=ProductInfo,
            model="gpt-4o-mini"
        )

        result = await self.execute_generation_async(request)

        if result.success:
            data = json.loads(result.content)
            return ProductInfo(**data)
        else:
            raise ValueError(f"Extraction failed: {result.error_message}")

    def analyze_sentiment(self, text: str) -> SentimentAnalysis:
        """Direct method using built-in schema."""
        from llmservice.structured_schemas import SentimentAnalysis

        request = GenerationRequest(
            user_prompt=text,
            response_schema=SentimentAnalysis
        )

        result = self.execute_generation(request)

        if result.success:
            data = json.loads(result.content)
            return SentimentAnalysis(**data)
```

#### Method 6: Complex Nested Schemas

```python
# Structured outputs support complex nested structures
from typing import List, Optional
from datetime import datetime

class Address(BaseModel):
    street: str
    city: str
    country: str
    zip_code: Optional[str] = None

class OrderItem(BaseModel):
    product_name: str
    quantity: int
    price: float

class Order(BaseModel):
    order_id: str
    customer_name: str
    items: List[OrderItem]
    shipping_address: Address
    total: float
    placed_at: datetime

# Extract complex order from unstructured text
order = engine.generate_structured(
    prompt="Order #12345 for John Doe, 2 iPhone 15 Pro at $999 each...",
    schema=Order
)

# Access nested data with full type safety
print(f"Customer: {order.customer_name}")
print(f"Ship to: {order.shipping_address.city}")
for item in order.items:  # Type-safe iteration
    print(f"  - {item.quantity}x {item.product_name}: ${item.price}")
```

#### Built-in Schema Library

```python
from llmservice.structured_schemas import (
    # Analysis schemas
    SemanticIsolation,      # Extract semantic elements
    EntitiesList,           # Named entity recognition
    SentimentAnalysis,      # Sentiment with scores
    Summary,                # Text summarization
    ChainOfThought,         # Step-by-step reasoning

    # Data extraction schemas
    KeyValuePairs,          # Extract key-value data
    Classification,         # Categorize content
    Translation,            # Language translation
)

# Use pre-built schemas
sentiment = engine.generate_structured(
    prompt="This product exceeded my expectations! Amazing quality.",
    schema=SentimentAnalysis
)
print(f"Sentiment: {sentiment.overall_sentiment}")  # "positive"
print(f"Confidence: {sentiment.scores.positive}")    # 0.95
```

#### Key Advantages of Structured Outputs

1. **Guaranteed Format** - No parsing errors, always valid JSON
2. **Type Safety** - IDE autocomplete and type checking
3. **Validation** - Pydantic validates all fields automatically
4. **Nested Support** - Complex hierarchical data structures
5. **Error Prevention** - Schema mismatches caught at runtime
6. **Cost Efficient** - LLM forced to output only required fields

#### Choosing the Right Method

| Use Case | Recommended Method |
|----------|-------------------|
| Simple extraction | Built-in methods (`semantic_isolation_v2`) |
| Custom data structure | `generate_structured()` or `process_with_schema()` |
| Service integration | `response_schema` in GenerationRequest |
| Async operations | `response_schema` with `execute_generation_async()` |
| Quick prototyping | Built-in schema library |
| Production systems | Custom Pydantic models with validation |

#### Migration from Pipelines

```python
# OLD PIPELINE WAY (Deprecated):
request = GenerationRequest(
    user_prompt="Extract the name",
    pipeline_config=[
        {'type': 'SemanticIsolation', 'params': {'element': 'name'}}
    ]
)

# NEW STRUCTURED WAY:
class NameExtraction(BaseModel):
    name: str = Field(description="The extracted name")

request = GenerationRequest(
    user_prompt="Extract the name",
    response_schema=NameExtraction  # Guaranteed structure
)

## 💡 Key Design Decisions

### Why Layered Architecture?

- **Separation of Concerns**: Each layer has one job
- **Testability**: Can test each layer independently
- **Flexibility**: Can swap implementations at any layer
- **Maintainability**: Changes are localized to specific layers

### Why So Many Data Classes?

- **Type Safety**: Clear contracts between layers
- **Documentation**: Data classes are self-documenting
- **Debugging**: Can inspect data at each transformation stage
- **Extensibility**: Easy to add new fields without breaking existing code

### Why Provider Abstraction?

- **Provider Independence**: Not locked into any AI service
- **Cost Optimization**: Can switch providers based on cost/performance
- **Fallback Options**: Can fail over to different providers
- **Testing**: Can mock providers for testing

## 🚀 Getting Started as a Developer

### Your First Custom Service

```python
from llmservice import BaseLLMService, GenerationRequest

class MyAIAssistant(BaseLLMService):
    def summarize(self, text: str) -> str:
        request = GenerationRequest(
            user_prompt=f"Summarize this text: {text}",
            model="gpt-4o-mini"
        )
        result = self.execute_generation(request)
        return result.content

# Use it
assistant = MyAIAssistant(max_rpm=10)  # Rate limited to 10 req/min
summary = assistant.summarize("Long article here...")
```

### Key Files to Understand First

1. **`schemas.py`** - All data structures (start here!)
2. **`base_service.py`** - Main service orchestration
3. **`generation_engine.py`** - Core processing logic
4. **`providers/base.py`** - Provider interface
5. **`examples/`** - Working examples to learn from

### Common Patterns You'll See

1. **Async Everything**: Most operations have async versions
   ```python
   result = service.execute_generation(request)        # Sync
   result = await service.execute_generation_async(request)  # Async
   ```

2. **Rich Metadata**: Every response includes detailed information
   ```python
   print(result.elapsed_time)  # How long it took
   print(result.usage["cost"])  # How much it cost
   print(result.retry_count)    # How many retries
   ```

3. **Graceful Degradation**: Failures are handled elegantly
   ```python
   if not result.success:
       fallback = result.error_message or "Service unavailable"
   ```

## 📊 Operational Excellence

### Built-in Monitoring

- **Real-time Metrics**: RPM, TPM, costs updated live
- **Performance Tracking**: Every operation is timed
- **Error Classification**: Different error types for different issues
- **Request Tracing**: Unique IDs for debugging

### Production-Ready Features

- **Rate Limiting**: Never exceed API limits
- **Retry Logic**: Automatic recovery from transient failures
- **Cost Control**: Set budgets and monitor spending
- **Concurrency Control**: Limit parallel requests
- **Graceful Shutdown**: Proper cleanup on exit

## 🎯 Philosophy

This codebase follows these principles:

1. **Make the right thing easy**: Common tasks should be simple
2. **Make the wrong thing hard**: Prevent misuse through design
3. **Fail gracefully**: Always provide useful error information
4. **Measure everything**: You can't optimize what you don't measure
5. **Abstract but don't hide**: Complexity is accessible when needed

## Next Steps

1. **Run the examples** in `examples/` to see the system in action
2. **Read the tests** to understand expected behavior
3. **Try creating a simple service** following the patterns above
4. **Explore the providers** to see how different APIs are handled
5. **Check the metrics** to understand operational behavior

Welcome to the team! This codebase is designed to make working with LLMs reliable, efficient, and enjoyable. Happy coding! 🚀