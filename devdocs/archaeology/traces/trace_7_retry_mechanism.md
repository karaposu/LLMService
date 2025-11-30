# Trace 7: Retry Mechanism

## Interface: Retry Logic in `LLMHandler`

### Entry Point
- **Location**: `llmservice/llm_handler.py:86-150`
- **Uses**: `tenacity` library for retry orchestration
- **Configuration**: Per-request and default settings

### Retry Architecture

#### Retry Configuration
```python
LLMHandler initialization:
├── self.number_of_retries = 2  # Default
├── self.show_logs = True
└── Per-request override:
    └── request.number_of_retries or self.number_of_retries
```

### Execution Flow

#### 1. Retry Wrapper Setup
```python
from tenacity import Retrying, stop_after_attempt, wait_random_exponential

retrying = Retrying(
    retry=retry_if_exception_type((
        HTTPStatusError,    # HTTP errors
        RateLimitError,     # 429 specifically
        APITimeoutError,    # Timeout
        APIConnectionError  # Network issues
    )),
    stop=stop_after_attempt(max_retries),
    wait=wait_random_exponential(min=1, max=60),
    reraise=True
)
```

**Key Parameters**:
- `retry`: Conditions that trigger retry
- `stop`: Maximum attempts (not retries)
- `wait`: Backoff strategy
- `reraise`: Final exception handling

#### 2. Retry Loop Execution
```
for attempt in retrying:
    ├── with attempt:
    │   ├── start_time = time.time()
    │   ├── provider._invoke_impl(payload)
    │   │   └── API call happens here
    │   ├── elapsed = time.time() - start_time
    │   └── Record attempt details
    │
    ├── On success:
    │   └── Break loop, return result
    │
    └── On retryable error:
        ├── Calculate backoff
        ├── Sleep
        └── Continue loop
```

**Attempt Recording**:
```python
attempt_info = {
    "attempt": attempt_number,
    "start_time": start_time,
    "end_time": end_time,
    "elapsed": elapsed,
    "success": success,
    "error": error_message if failed
}
attempts.append(attempt_info)
```

#### 3. Backoff Calculation
```
wait_random_exponential(min=1, max=60)
├── base_wait = 2^attempt  # Exponential
├── jitter = random() * base_wait  # Randomization
├── final_wait = min(max(jitter, 1), 60)  # Bounded
└── sleep(final_wait)
```

**Backoff Pattern**:
```
Attempt 1 fails → Wait 1-2 seconds
Attempt 2 fails → Wait 2-4 seconds
Attempt 3 fails → Wait 4-8 seconds
Attempt 4 fails → Wait 8-16 seconds
Attempt 5 fails → Wait 16-32 seconds
Attempt 6+ fails → Wait 32-60 seconds
```

### Error Classification

#### Retryable Errors
```python
# These trigger automatic retry:
HTTPStatusError with codes:
├── 429: Rate limit exceeded
├── 500: Internal server error
├── 502: Bad gateway
├── 503: Service unavailable
└── 504: Gateway timeout

APITimeoutError:
├── Request timeout
├── Read timeout
└── Connection timeout

APIConnectionError:
├── Connection refused
├── DNS failure
└── Network unreachable
```

#### Non-Retryable Errors
```python
# These fail immediately:
PermissionDeniedError:
├── 401: Invalid API key
├── 403: Forbidden
└── "insufficient_quota"

ValidationError:
├── 400: Bad request
├── 422: Unprocessable entity
└── Schema mismatch

NotFoundError:
├── 404: Model not found
└── Endpoint not found
```

### Retry Coordination with Rate Limiting

#### Interaction Pattern
```
Request Flow:
├── 1. Pass rate limit gate
├── 2. Mark request sent
├── 3. Try API call
├── 4a. Success → Mark received
└── 4b. Rate limit error (429)
    ├── Retry mechanism triggers
    ├── Exponential backoff
    ├── Don't unmark sent (still counting)
    └── Retry (may hit rate gate again)
```

**Why Double Protection**:
1. Local rate gate prevents most 429s
2. Retry handles provider-side rate limits
3. Prevents cascade failures

### Async Retry Flow

#### AsyncRetrying Setup
```python
from tenacity import AsyncRetrying

async_retrying = AsyncRetrying(
    # Same configuration as sync
    retry=retry_if_exception_type(...),
    stop=stop_after_attempt(max_retries),
    wait=wait_random_exponential(min=1, max=60)
)
```

#### Async Execution
```python
async for attempt in async_retrying:
    async with attempt:
        start_time = time.time()
        response = await provider._invoke_async_impl(payload)
        # Async sleep during backoff
```

**Key Difference**:
- `await` during API call
- `await asyncio.sleep()` during backoff
- Non-blocking throughout

### Retry Statistics

#### Metrics Collection
```python
BackoffStats populated:
├── retry_count: Total retry attempts
├── total_backoff_ms: Sum of wait times
├── max_backoff_ms: Longest single wait
└── final_attempt: Which attempt succeeded
```

#### Result Enrichment
```python
GenerationResult includes:
├── attempts: List of all attempts
│   ├── Each with timing info
│   ├── Success/failure status
│   └── Error details if failed
│
├── retry_count: Number of retries
├── total_time: Including all retries
└── success: Final outcome
```

### Special Cases

#### Insufficient Quota Handling
```python
except PermissionDeniedError as e:
    if "insufficient_quota" in str(e):
        # Don't retry - permanent failure
        return (None, False, ErrorType.INSUFFICIENT_QUOTA)
    # Check for region restrictions
    elif "unsupported_country" in str(e):
        return (None, False, ErrorType.UNSUPPORTED_REGION)
```

**Behavior**:
- No retry attempts
- Immediate failure
- Clear error type

#### Timeout Handling
```python
# Request timeout vs retry timeout:
Request timeout: 600s (10 minutes) - single attempt
Retry timeout: None - controlled by max_attempts
Total possible time: 600s * 3 attempts = 30 minutes
```

### Observable Behavior

#### Logging Output
```
When show_logs=True:
INFO: Attempt 1/3 for request_12345
WARNING: Attempt 1 failed: 429 Rate limit exceeded
INFO: Waiting 2.3s before retry
INFO: Attempt 2/3 for request_12345
INFO: Attempt 2 succeeded in 1.5s
```

#### User Experience
```
From user perspective:
├── Single request appears to take longer
├── No error if retry succeeds
├── Transparent recovery
└── Only final error if all retries fail
```

### Retry Optimization

#### Adaptive Retry Strategy
```python
# Could be enhanced to:
if error_code == 429:
    # Extract Retry-After header
    retry_after = response.headers.get("Retry-After", 60)
    wait_time = max(retry_after, calculated_backoff)
```

#### Circuit Breaker Pattern
```python
# Could add circuit breaker:
if consecutive_failures > threshold:
    # Stop attempting for cool-down period
    circuit_open = True
    raise CircuitOpenError()
```

### Cost Implications

#### Retry Costs
```
Each retry:
├── Input tokens charged again
├── Output tokens if partial response
├── Increased latency
└── Rate limit consumption
```

#### Cost Tracking
```python
# Costs only recorded on success:
if attempt.is_successful:
    metrics.mark_rcv(tokens, cost)
# Failed attempts not charged
```

### Why This Design

1. **Automatic Recovery**: Handles transient failures transparently
2. **Exponential Backoff**: Prevents overwhelming provider
3. **Jitter**: Prevents thundering herd
4. **Configurable**: Per-request retry control
5. **Observable**: Detailed attempt tracking

### Configuration Examples

#### Conservative Retry
```python
GenerationRequest(
    number_of_retries=0  # No retries
)
# Fails fast on any error
```

#### Aggressive Retry
```python
GenerationRequest(
    number_of_retries=5  # 6 total attempts
)
# Maximum resilience
```

#### Default Balanced
```python
# number_of_retries=2 (3 total attempts)
# Good balance of resilience and latency
```

### Implementation Details

**Tenacity Integration**:
```python
# Tenacity handles:
- Exception catching
- Backoff calculation
- Sleep management
- Attempt counting
- Statistics collection
```

**Thread Safety**:
- Each handler has own retry state
- No shared retry counters
- Thread-local retry objects

**Memory Management**:
- Attempts list bounded by max_retries
- No unbounded growth
- Automatic cleanup on completion