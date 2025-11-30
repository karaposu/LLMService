# LLMService Examples

This folder contains modern examples demonstrating the latest features of LLMService, replacing the deprecated pipeline-based approach with structured outputs using Pydantic schemas.

## 🚀 What's New

These examples showcase the migration from the old pipeline system to the new structured output approach:

### Old Way (Deprecated):
```python
pipeline_config = [{
    'type': 'SemanticIsolation',
    'params': {'semantic_element_for_extraction': 'specific_data'}
}]
```

### New Way (Current):
```python
from pydantic import BaseModel

class MySchema(BaseModel):
    specific_data: str

result = engine.generate_structured(prompt, schema=MySchema)
```

## 📚 Examples

### 1. Capital Finder
**Location:** `capital_finder/`

Demonstrates:
- Basic text generation
- Structured output for data extraction
- Batch processing
- Usage statistics tracking

**Run:**
```bash
python examples/capital_finder/main.py
```

**Key Features:**
- Extract just capital names using structured schemas
- Get detailed country information with optional fields
- Shows both `generate_structured()` and `GenerationRequest` approaches

### 2. SQL Code Generator
**Location:** `SQL_code_generator/`

Demonstrates:
- Natural language to SQL conversion
- Complex structured outputs with explanations
- Query optimization suggestions
- Batch query generation

**Run:**
```bash
python examples/SQL_code_generator/main.py
```

**Key Features:**
- Clean SQL extraction without surrounding text
- Performance analysis and index recommendations
- Multiple output formats (simple, with explanation, optimized)

### 3. Translator
**Location:** `translator/`

Demonstrates:
- Multi-language translation
- Async batch processing for efficiency
- Translation with metadata (confidence, alternatives)
- Context-aware translation

**Run:**
```bash
python examples/translator/main.py
```

**Key Features:**
- Parallel translation using async/await
- Document translation with formatting preservation
- Contextual disambiguation (e.g., "bank" as institution vs. riverbank)

## 🔧 Setup

1. **Install LLMService:**
   ```bash
   pip install llmservice
   # OR from source:
   pip install -e .
   ```

2. **Set up API Key:**
   Create a `.env` file in your project root:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

3. **Run Examples:**
   ```bash
   cd examples
   python capital_finder/main.py
   ```

## 💡 Key Concepts

### Structured Outputs
All examples use Pydantic models to define expected output structure:

```python
from pydantic import BaseModel, Field

class OutputSchema(BaseModel):
    field1: str = Field(description="Description of field1")
    field2: int = Field(ge=0, le=100)  # With constraints
    field3: Optional[List[str]] = None  # Optional field
```

### Two Approaches

#### Approach 1: Using GenerationEngine directly
```python
engine = GenerationEngine(model_name="gpt-4o-mini")
result = engine.generate_structured(
    prompt="Your prompt",
    schema=YourSchema,
    system="System instructions"
)
# Returns parsed Pydantic model directly
```

#### Approach 2: Using GenerationRequest
```python
request = GenerationRequest(
    user_prompt="Your prompt",
    response_schema=YourSchema,
    model="gpt-4o-mini"
)
result = service.execute_generation(request)
# Returns GenerationResult with JSON in result.content
```

### Rate Limiting
All examples include rate limiting to prevent API throttling:

```python
service = MyLLMService(
    max_rpm=30,      # 30 requests per minute
    max_tpm=10000,   # 10,000 tokens per minute
    max_concurrent_requests=5
)
```

### Async Processing
For batch operations, use async for parallel processing:

```python
async def batch_process(items):
    tasks = [process_async(item) for item in items]
    results = await asyncio.gather(*tasks)
    return results
```

## 📊 Monitoring

Each example includes usage statistics:
- Request counts
- Token usage
- Cost estimates
- Performance metrics

## 🔄 Migration from Old Examples

If you're migrating from the deprecated examples:

1. **Replace pipeline configs** with Pydantic schemas
2. **Use `generate_structured()`** instead of pipeline processing
3. **Define explicit schemas** for all structured data extraction
4. **Leverage async** for batch operations
5. **Add rate limiting** to prevent API throttling

## 📝 Best Practices

1. **Always use structured outputs** when you need specific data format
2. **Define schemas clearly** with descriptions and constraints
3. **Handle exceptions** - structured output can fail on complex schemas
4. **Use appropriate models** - gpt-4o-mini for simple tasks, gpt-4o for complex
5. **Monitor costs** - track token usage and costs in production
6. **Implement rate limiting** - protect against API rate limits
7. **Use async for batches** - much more efficient than sequential calls

## 🆘 Troubleshooting

**Import Error:**
Make sure llmservice is installed and in your Python path.

**API Key Error:**
Check that OPENAI_API_KEY is set in your environment or .env file.

**Rate Limit Error:**
Reduce max_rpm/max_tpm or add delays between requests.

**Structured Output Parse Error:**
Ensure your schema is well-defined and the model can understand it.

## 📚 Learn More

- See the main README for library documentation
- Check `devdocs/` for architecture details
- Review test files for more usage patterns