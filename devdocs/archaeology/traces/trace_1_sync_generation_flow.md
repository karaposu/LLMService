# Trace 1: Synchronous Generation Flow

## Interface: `BaseLLMService.execute_generation()`

### Entry Point
- **Caller**: User application code (e.g., `MyLLMService` subclass)
- **Input**: `GenerationRequest` containing prompts, schemas, and configuration
- **Location**: `llmservice/base_service.py:136`

### Execution Path

#### 1. Request Initialization
```
BaseLLMService.execute_generation(generation_request, operation_name)
├── _new_trace_id() → generates UUID for tracing
├── get_current_rpm() → captures pre-execution RPM
└── get_current_tpm() → captures pre-execution TPM
```

**State Changes**:
- `trace_id` generated for request tracking
- Request metadata enriched with `operation_name` and `request_id`
- Timestamp recorded at `generation_enqueued_at`

#### 2. Rate Limiting Gates
```
_rpm_gate.wait_if_rate_limited_sync(metrics)
├── MetricsRecorder.is_rpm_limited() → checks sliding window
├── _secs_until_refresh() → calculates wait time
└── time.sleep() → blocks thread if needed

_tpm_gate.wait_if_token_limited_sync(metrics)
├── MetricsRecorder.is_tpm_limited() → checks token window
├── _secs_until_refresh() → calculates wait time
└── time.sleep() → blocks thread if needed
```

**Data Flow**:
- `metrics.sent_ts` deque consulted for RPM calculation
- `metrics.tok_ts` deque consulted for TPM calculation
- Wait loops tracked in `rpm_wait_loops`, `tpm_wait_loops`
- Wait time accumulated in `rpm_waited_ms`, `tpm_waited_ms`

**State Changes**:
- Thread blocks until rate limits allow progression
- `generation_dequeued_at` timestamp recorded after gates

#### 3. Metrics Pre-Registration
```
metrics.mark_sent(trace_id)
├── Appends to sent_ts deque
├── Increments total_sent counter
└── Adds trace_id to sent_ids
```

**State Changes**:
- Request counted in sliding window
- Total request counter incremented

#### 4. Generation Engine Processing
```
generation_engine.generate_output(generation_request)
├── _convert_to_llm_call_request()
│   ├── Converts GenerationRequest → LLMCallRequest
│   ├── Renames 'model' → 'model_name'
│   └── Drops business fields (operation_name, request_id)
│
├── _execute_llm_call(llm_call_request)
│   ├── llm_handler.process_call_request()
│   │   ├── provider.convert_request() → provider-specific format
│   │   └── Retrying loop with exponential backoff
│   │       └── provider._invoke_impl() → actual API call
│   │
│   └── _build_generation_result()
│       ├── Extracts content from response
│       ├── Calculates costs
│       └── Builds GenerationResult object
│
└── Returns GenerationResult
```

**Data Transformations**:
1. `GenerationRequest` → `LLMCallRequest` (field mapping)
2. `LLMCallRequest` → Provider payload (API-specific)
3. Provider response → `InvokeResponseData` (standardized)
4. `InvokeResponseData` → `GenerationResult` (enriched)

#### 5. Post-Processing
```
_after_response(result)
├── metrics.mark_rcv(trace_id, tokens, cost)
│   ├── Updates rcv_ts deque
│   ├── Updates tok_ts with token count
│   └── Accumulates total_cost
│
└── usage_stats.update(usage, operation_name)
    └── Aggregates per-operation statistics
```

**State Changes**:
- Response metrics recorded
- Cost accumulated
- Operation-specific usage tracked

#### 6. Result Enrichment
```
result.enrichment
├── Adds trace_id
├── Adds backoff statistics (rpm_loops, tpm_loops, wait times)
├── Adds timestamps (enqueued_at, dequeued_at, completed_at)
├── Adds rate metrics (rpm_at_beginning, rpm_at_end)
└── Calculates elapsed_time
```

**Final Output**:
- `GenerationResult` with complete telemetry
- Contains: content, usage, costs, timings, rate info

### Error Handling Paths

#### Rate Limit Error Path
```
If provider returns 429:
├── metrics.unmark_sent(trace_id) → reverses counter
├── Retry mechanism triggers
├── Exponential backoff applied
└── Request resubmitted (up to max_retries)
```

#### Provider Error Path
```
If provider returns error:
├── Error classified (ErrorType enum)
├── result.success = False
├── result.error_message populated
├── metrics.unmark_sent(trace_id) if permanent failure
└── Returns failed GenerationResult
```

### Resource Management

**Thread Safety**:
- `metrics._lock` protects all metric operations
- `usage_stats` updates are atomic
- Rate gates use thread-safe deques

**Memory Management**:
- Sliding windows auto-trim old entries
- Deques have implicit size limits
- No unbounded growth structures

### Performance Characteristics

**Blocking Points**:
1. Rate limit gates (potentially seconds)
2. Provider API call (network latency)
3. Retry backoff (exponential delays)

**Optimization Points**:
- Pre-calculated sliding windows
- Cached provider instances
- Reused HTTP connections

### Observable Effects

**Metrics Updated**:
- `total_sent`, `total_rcv` counters
- RPM/TPM sliding windows
- `total_cost` accumulator
- Per-operation usage statistics

**Logs Emitted**:
- Rate limit warnings
- Retry attempts
- Operation completions (if show_logs=True)

**External Calls**:
- OpenAI/Claude/Ollama API endpoints
- No other external dependencies

### Why This Design

1. **Rate Limiting Before API Call**: Prevents 429 errors proactively
2. **Trace ID Throughout**: Enables request correlation across logs
3. **Metrics at Entry/Exit**: Captures both attempts and successes
4. **Synchronous Blocking**: Simpler error handling, predictable flow
5. **Rich Telemetry**: Supports production debugging and optimization