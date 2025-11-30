# Trace 5: Structured Output Processing

## Interface: Schema-based Generation

### Entry Points
Multiple entry points for structured output:
1. `GenerationRequest.response_schema` - Direct schema specification
2. `GenerationEngine.process_with_schema()` - Auto-parsed result
3. `GenerationEngine.generate_structured()` - Alias for above
4. `GenerationEngine.semantic_isolation_v2()` - Built-in extraction

### Execution Path

#### 1. Schema Specification (User Layer)
```
User Code:
├── Define Pydantic model
│   class ProductInfo(BaseModel):
│       name: str
│       price: float
│       in_stock: bool
│
└── Attach to request
    GenerationRequest(
        user_prompt="Extract product info",
        response_schema=ProductInfo
    )
```

#### 2. Schema Validation (Engine Layer)
```
GenerationEngine.generate_output(request)
├── if request.response_schema:
│   ├── Validate is Pydantic BaseModel
│   ├── Set output_type = "json"
│   └── Pass schema through conversion
```

#### 3. Schema to JSON Schema (Provider Layer)
```
ResponsesAPIProvider.convert_request(llm_request)
├── if llm_request.response_schema:
│   ├── schema_dict = llm_request.response_schema.model_json_schema()
│   │   └── Pydantic generates JSON Schema
│   │
│   ├── payload["text"] = {
│   │       "format": {
│   │           "type": "json_schema",
│   │           "schema": schema_dict
│   │       }
│   │   }
│   │
│   └── payload["reasoning"] = {"effort": "low"}
│       └── Low reasoning for better format compliance
```

**Schema Transformation**:
```python
Pydantic Model:
class ProductInfo(BaseModel):
    name: str = Field(description="Product name")
    price: float = Field(ge=0)
    in_stock: bool

↓ model_json_schema() ↓

JSON Schema:
{
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Product name"
        },
        "price": {
            "type": "number",
            "minimum": 0
        },
        "in_stock": {
            "type": "boolean"
        }
    },
    "required": ["name", "price", "in_stock"]
}
```

#### 4. API Request with Schema
```
OpenAI API Request:
{
    "model": "gpt-4o-mini",
    "input": "iPhone 15 Pro costs $999 and is available",
    "instructions": "Extract product information",
    "text": {
        "format": {
            "type": "json_schema",
            "schema": {...}  // JSON Schema
        }
    },
    "reasoning": {"effort": "low"}
}
```

**API Behavior**:
- Model forced to output valid JSON
- Schema enforced during generation
- No free-form text allowed
- Guaranteed parse-able response

#### 5. Response Processing
```
Provider Response:
├── response.output[0].content[0].text
│   └── '{"name":"iPhone 15 Pro","price":999,"in_stock":true}'
│
├── Already valid JSON (guaranteed by API)
├── No parsing errors possible
└── Set response_type = "json"
```

#### 6. Result Building
```
GenerationEngine._build_generation_result()
├── if request.output_type == "json":
│   ├── result.content = response_text  # JSON string
│   ├── result.response_type = "json"
│   └── result.success = True
```

### Auto-Parsing Path (`process_with_schema`)

#### Different Entry, Same Core
```
engine.process_with_schema(content, schema, instructions)
├── Create GenerationRequest
│   ├── user_prompt = content
│   ├── system_prompt = instructions
│   └── response_schema = schema
│
├── result = generate_output(request)
│   └── [Same structured output flow]
│
└── Parse and return Pydantic model
    ├── data = json.loads(result.content)
    └── return schema(**data)  # Pydantic instance
```

**Key Difference**:
- `generate_output()` returns JSON string
- `process_with_schema()` returns parsed Pydantic model

### Built-in Schema Processing

#### Semantic Isolation
```
engine.semantic_isolation_v2(content, element="symptoms")
├── Use predefined SemanticIsolation schema
│   class SemanticIsolation(BaseModel):
│       answer: str
│
├── process_with_schema(
│       content=content,
│       schema=SemanticIsolation,
│       instructions=f"Extract: {element}"
│   )
│
└── return result.answer  # Just the string
```

#### Entity Extraction
```
engine.extract_entities(text)
├── Use predefined EntitiesList schema
│   class EntitiesList(BaseModel):
│       entities: List[Entity]
│
├── process_with_schema(
│       content=text,
│       schema=EntitiesList,
│       instructions="Extract named entities"
│   )
│
└── return [e.dict() for e in result.entities]
```

### Schema Enforcement Mechanism

#### At API Level (Responses API)
```
OpenAI Processing:
├── Parse JSON Schema
├── Build constrained decoder
├── Generate tokens with constraints
│   ├── Only valid property names
│   ├── Type-appropriate values
│   └── Required fields enforced
└── Output guaranteed valid JSON
```

#### Fallback for Non-Structured Models
```
If model doesn't support structured output:
├── System prompt includes schema
├── Few-shot examples provided
├── Best-effort JSON generation
└── May require parsing/validation
```

### Error Handling

#### Schema Validation Errors
```
try:
    schema(**data)
except ValidationError as e:
    # Should never happen with structured output
    # But handled for robustness
    raise ValueError(f"Schema validation failed: {e}")
```

#### Invalid Schema Definition
```
if not issubclass(schema, BaseModel):
    raise ValueError("Schema must be Pydantic BaseModel")
```

### Performance Optimization

#### Reasoning Effort Control
```
# For structured output, use low reasoning:
if response_schema:
    reasoning_effort = "low"

Why: Low reasoning improves format compliance
     High reasoning may "overthink" structure
```

#### Schema Caching
```python
# Pydantic caches schema generation:
@lru_cache
def model_json_schema():
    # Schema only computed once per model class
```

### Observable Effects

#### Response Characteristics
```
Without Schema:
- Variable format
- May include explanations
- Requires parsing
- May fail validation

With Schema:
- Exact format guaranteed
- No extraneous text
- Direct JSON parsing
- Validation always passes
```

#### Cost Implications
```
Structured Output:
- Fewer output tokens (no fluff)
- Lower reasoning tokens (low effort)
- More predictable costs
- Faster generation
```

### Complex Schema Support

#### Nested Structures
```python
class Address(BaseModel):
    street: str
    city: str

class Order(BaseModel):
    items: List[OrderItem]
    shipping: Address

# Fully supported - generates nested JSON
```

#### Optional Fields
```python
class Response(BaseModel):
    required: str
    optional: Optional[str] = None

# API ensures required fields
# Optional fields may be omitted
```

#### Enums and Constraints
```python
class Status(str, Enum):
    PENDING = "pending"
    COMPLETE = "complete"

class Task(BaseModel):
    status: Status
    priority: int = Field(ge=1, le=5)

# Enforced during generation
```

### Why This Design

1. **Guaranteed Parsing**: No more JSON decode errors
2. **Type Safety**: Pydantic validation built-in
3. **API-Native**: Leverages provider capabilities
4. **Cost Efficient**: Minimal tokens for structure
5. **Developer Experience**: Define schema, get typed result

### Migration from Pipelines

#### Old Pipeline Approach
```python
# Complex, error-prone:
pipeline_config=[
    {'type': 'GenerateJSON'},
    {'type': 'ParseJSON'},
    {'type': 'ValidateSchema'},
    {'type': 'ExtractField'}
]
```

#### New Structured Approach
```python
# Simple, reliable:
response_schema=MySchema
# That's it - everything handled
```

### Implementation Notes

**Strict Mode**:
```python
strict_mode = True  # Default
# Ensures 100% schema compliance
# May reject edge cases
```

**Parse Response Flag**:
```python
parse_response = True  # In GenerationRequest
# Controls auto-parsing behavior
# Set False for raw JSON string
```

**Schema Introspection**:
```python
# System can inspect schema:
fields = schema.model_fields
required = schema.model_fields_required
# Used for prompt generation if needed
```