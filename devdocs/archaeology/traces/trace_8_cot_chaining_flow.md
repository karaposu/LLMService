# Trace 8: Chain-of-Thought (CoT) Chaining Flow

## Interface: `GenerationEngine.generate_with_cot_chain()`

### Entry Point
- **Location**: `llmservice/generation_engine.py:157`
- **Purpose**: Link multiple requests for stateful conversation
- **Uses**: Responses API's response_id feature

### Execution Path

#### 1. Initial CoT Request
```
generate_with_cot_chain(request, previous_response_id=None)
├── request.previous_response_id = None  # First in chain
├── generate_output(request)
│   ├── Standard generation flow
│   └── Returns GenerationResult with response_id
│
└── result.response_id = "resp_abc123"  # From API
```

**Response ID Source**:
```python
# From ResponsesAPIProvider:
response = client.responses.create(...)
response_id = response.id  # "resp_abc123"
```

#### 2. Chained Request
```
generate_with_cot_chain(request2, previous_response_id="resp_abc123")
├── request2.previous_response_id = "resp_abc123"
├── generate_output(request2)
│   ├── LLMCallRequest.previous_response_id = "resp_abc123"
│   └── Provider adds to API payload
│
└── API request includes context reference
```

**API Payload with Chaining**:
```json
{
    "model": "gpt-4o-mini",
    "input": "Follow-up question",
    "previous_response_id": "resp_abc123"
}
```

#### 3. Provider-Level Handling
```
ResponsesAPIProvider.convert_request(llm_request)
├── if llm_request.previous_response_id:
│   └── payload["previous_response_id"] = llm_request.previous_response_id
```

**API Behavior**:
- Links to previous context
- Maintains conversation state
- Accesses prior reasoning
- Preserves variable bindings

### State Management

#### What's Preserved
```
Between chained requests:
├── Conversation context
├── Reasoning steps
├── Defined variables
├── Established facts
└── Decision history
```

#### What's Not Preserved
```
Not carried over:
├── Rate limit state
├── Metrics/telemetry
├── Error history
├── Cost accumulation
└── Retry attempts
```

### Use Cases

#### Multi-Step Reasoning
```python
# Step 1: Analyze problem
result1 = engine.generate_with_cot_chain(
    GenerationRequest(
        user_prompt="Break down this problem: ..."
    )
)

# Step 2: Solve using analysis
result2 = engine.generate_with_cot_chain(
    GenerationRequest(
        user_prompt="Now solve step by step"
    ),
    previous_response_id=result1.response_id
)
```

#### Iterative Refinement
```python
# Initial generation
result = engine.generate_with_cot_chain(request)

# Refinements
for refinement in refinements:
    result = engine.generate_with_cot_chain(
        refinement_request,
        previous_response_id=result.response_id
    )
```

### Chain Breaking Conditions

#### When Chains Break
```
Chain breaks if:
├── response_id is None (model doesn't support)
├── Invalid response_id provided
├── Different model used
├── Too much time elapsed (provider-dependent)
└── Response_id expired (provider cleanup)
```

#### Fallback Behavior
```python
if not previous_response_id:
    # Treat as independent request
    # No context preservation
    # Fresh reasoning
```

### Observable Effects

#### Response Characteristics
```
Without Chaining:
- No context from previous
- Repeats information
- May contradict earlier

With Chaining:
- Refers to "as I mentioned"
- Consistent reasoning
- Builds on previous
```

#### Performance Impact
```
Chained requests:
├── Slightly higher latency (context loading)
├── More tokens used (context inclusion)
├── Higher cost (reasoning preservation)
└── Better coherence
```

### Why This Design

1. **Stateful Reasoning**: Complex multi-step problems
2. **Context Preservation**: No need to repeat
3. **API-Native**: Uses provider features
4. **Optional**: Works without if not supported
5. **Explicit**: User controls chaining

### Limitations

- Only works with Responses API models
- Chain depth provider-limited
- No cross-model chaining
- Response IDs expire