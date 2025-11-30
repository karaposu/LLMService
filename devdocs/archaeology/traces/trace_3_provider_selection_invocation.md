# Trace 3: Provider Selection and Invocation

## Interface: `LLMHandler.process_call_request()`

### Entry Point
- **Caller**: `GenerationEngine._execute_llm_call()`
- **Input**: `LLMCallRequest` with model_name and prompt data
- **Location**: `llmservice/llm_handler.py:66`

### Execution Path

#### 1. Model Change Detection
```
process_call_request(request)
├── if request.model_name != self.model_name:
│   └── change_model(model_name)
│       ├── self.model_name = model_name
│       └── self.provider = ResponsesAPIProvider(model_name)
│           ├── Instantiates new provider
│           ├── self.client = OpenAI(api_key=key)
│           └── self.async_client = AsyncOpenAI(api_key=key)
```

**Provider Selection Logic**:
Currently hardcoded to `ResponsesAPIProvider` only. Legacy multi-provider selection removed:
```python
# Old logic (removed):
if model_name.startswith("gpt"):
    provider = OpenAIProvider()
elif model_name.startswith("claude"):
    provider = ClaudeProvider()
```

#### 2. Request Conversion
```
provider.convert_request(request)
├── _build_input(request)
│   ├── Determines format (string vs messages array)
│   ├── Handles multimodal content
│   └── Returns input structure
│
├── Build base payload
│   ├── "model": model_name
│   ├── "input": input_content
│   └── "instructions": system_prompt
│
├── Add reasoning control (if applicable)
│   └── "reasoning": {"effort": "low|medium|high"}
│
├── Add structured output (if schema present)
│   └── "text": {"format": json_schema}
│
└── Returns provider-specific payload
```

**Data Transformation**:
```python
LLMCallRequest {
    user_prompt: "Question?",
    system_prompt: "Be helpful",
    response_schema: MySchema
}
↓
ResponsesAPI Payload {
    "model": "gpt-4o-mini",
    "input": "Question?",
    "instructions": "Be helpful",
    "text": {
        "format": {
            "type": "json_schema",
            "schema": {...}
        }
    }
}
```

#### 3. Retry Loop Execution
```
Retrying(
    retry=retry_if_exception_type((HTTPStatusError, RateLimitError)),
    stop=stop_after_attempt(max_retries),
    wait=wait_random_exponential(min=1, max=60)
):
    └── for attempt in retrying:
        ├── Record attempt start time
        ├── provider._invoke_impl(payload)
        │   └── client.responses.create(**payload)
        │       └── HTTP POST to OpenAI API
        ├── Record attempt end time
        └── Handle success or exception
```

**Retry Behavior**:
- Retries on: 429 (rate limit), 500-503 (server errors)
- Does not retry on: 400 (bad request), 401 (auth), 404 (not found)
- Exponential backoff with jitter: 1-60 seconds
- Maximum 2 retries by default (3 total attempts)

#### 4. Provider Invocation
```
provider._invoke_impl(payload)
├── try:
│   └── response = client.responses.create(**payload)
│       ├── Validates payload structure
│       ├── Makes HTTPS request
│       ├── Waits for response
│       └── Returns Response object
│
├── except RateLimitError:
│   └── raise for retry mechanism
│
├── except PermissionDeniedError as e:
│   ├── Check error message
│   ├── Classify error type
│   └── return (None, False, ErrorType.INSUFFICIENT_QUOTA)
│
└── except Exception:
    └── raise for retry mechanism
```

**API Communication**:
- Uses OpenAI Python SDK
- HTTPS with automatic retries
- Connection pooling enabled
- Timeout: 600 seconds default

#### 5. Response Processing
```
After successful invocation:
├── provider.extract_usage(response)
│   ├── response.usage.input_tokens
│   ├── response.usage.output_tokens
│   ├── response.usage.reasoning_tokens
│   ├── response.output_text → content
│   └── response.id → response_id
│
├── provider.calculate_cost(model, usage)
│   ├── Look up model costs
│   ├── input_tokens * input_cost
│   ├── output_tokens * output_cost
│   ├── reasoning_tokens * reasoning_cost
│   └── Returns cost breakdown
│
└── Build InvokeResponseData
    ├── success: true
    ├── response: raw response
    ├── attempts: list of attempts
    ├── usage: enriched with costs
    └── error_type: None
```

### Provider Abstraction Pattern

#### Base Provider Interface
```python
class BaseLLMProvider(ABC):
    @abstractmethod
    def supports_model(cls, model_name: str) -> bool

    @abstractmethod
    def convert_request(self, request: LLMCallRequest) -> Any

    @abstractmethod
    def _invoke_impl(self, payload: Any) -> Tuple[Any, bool, Optional[ErrorType]]

    @abstractmethod
    def extract_usage(self, response: Any) -> Dict[str, Any]

    @abstractmethod
    def calculate_cost(self, usage: Dict) -> Tuple[float, float]
```

#### Provider-Specific Implementation
```
ResponsesAPIProvider
├── Supports: gpt-4*, gpt-5*, o1* models
├── Uses: OpenAI Responses API
├── Special: reasoning tokens, CoT support
└── Format: Responses API JSON structure

ClaudeProvider (if implemented)
├── Supports: claude-* models
├── Uses: Anthropic API
├── Special: Different message format
└── Format: Anthropic JSON structure
```

### Cost Calculation

#### Model Pricing Table
```python
MODEL_COSTS = {
    'gpt-4o-mini': {
        'input_token_cost': 0.15e-6,   # $0.15/1M
        'output_token_cost': 0.6e-6,    # $0.60/1M
        'reasoning_token_cost': 0
    },
    'gpt-5': {
        'input_token_cost': 30e-6,      # $30/1M
        'output_token_cost': 60e-6,     # $60/1M
        'reasoning_token_cost': 45e-6   # $45/1M
    }
}
```

#### Cost Calculation Flow
```
calculate_cost(model="gpt-4o-mini", usage={input: 100, output: 200})
├── costs = MODEL_COSTS["gpt-4o-mini"]
├── input_cost = 100 * 0.15e-6 = $0.000015
├── output_cost = 200 * 0.6e-6 = $0.00012
└── total_cost = $0.000135
```

### Error Classification

#### Error Type Mapping
```
API Error → ErrorType Classification:
├── "unsupported_country_region" → UNSUPPORTED_REGION
├── "insufficient_quota" → INSUFFICIENT_QUOTA
├── HTTP 429 → HTTP_429
├── Connection error → NO_INTERNET_ACCESS
└── Other → UNKNOWN_OPENAI_ERROR
```

#### Error Handling Strategy
```
Transient Errors (Retry):
├── Rate limit (429)
├── Server errors (500-503)
├── Network timeout
└── Connection reset

Permanent Errors (Fail):
├── Invalid API key (401)
├── Invalid model (404)
├── Schema validation (400)
└── Insufficient quota
```

### Observable Effects

#### Metrics Impact
- Each attempt recorded with timing
- Successful responses update token counts
- Failed attempts tracked separately
- Costs accumulated only on success

#### Resource Usage
- New HTTP connection per provider change
- Connection pool maintained per client
- Memory for response buffering
- CPU for JSON parsing

### Why This Design

1. **Provider Abstraction**: Allows different AI services without changing caller code
2. **Retry Logic**: Handles transient failures automatically
3. **Cost Tracking**: Enables budget management and optimization
4. **Error Classification**: Allows appropriate handling strategies
5. **Model Switching**: Dynamic provider selection without restart

### Implementation Notes

**HTTP Client Configuration**:
```python
# In OpenAI client initialization:
timeout=httpx.Timeout(600.0, connect=5.0)
max_retries=0  # We handle retries ourselves
```

**Response Structure**:
```python
# Responses API response:
Response(
    id="resp_123",
    output=[
        ResponseOutputMessage(
            content=[OutputText(text="Answer")]
        )
    ],
    usage=Usage(input_tokens=10, output_tokens=20)
)
```

**Thread Safety**:
- Provider instance not shared between threads
- Each handler has its own provider
- Client libraries handle their own thread safety