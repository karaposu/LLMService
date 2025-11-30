# Trace 2: Asynchronous Generation Flow

## Interface: `BaseLLMService.execute_generation_async()`

### Entry Point
- **Caller**: Async user code (e.g., web handlers, async services)
- **Input**: `GenerationRequest` with same structure as sync
- **Location**: `llmservice/base_service.py:221`

### Execution Path

#### 1. Async Initialization
```
async execute_generation_async(generation_request, operation_name)
├── _new_trace_id() → generates UUID (synchronous)
├── get_current_rpm() → captures RPM (synchronous)
└── get_current_tpm() → captures TPM (synchronous)
```

**Key Difference from Sync**:
- Entry is async but initial operations are synchronous
- No await needed for metric snapshots

#### 2. Async Rate Limiting
```
await _rpm_gate.wait_if_rate_limited(metrics)
├── async with self._lock → asyncio.Lock acquisition
├── metrics.is_rpm_limited() → check (synchronous)
├── await asyncio.sleep(wait_s) → non-blocking wait
└── Updates _waiters_count for coordination

await _tpm_gate.wait_if_token_limited(metrics)
├── async with self._lock → asyncio.Lock acquisition
├── metrics.is_tpm_limited() → check (synchronous)
├── await asyncio.sleep(wait_s) → non-blocking wait
└── Updates _waiters_count for coordination
```

**Async Behavior**:
- Multiple coroutines can wait concurrently
- `_waiters_count` tracks waiting coroutines
- Event loop continues while waiting
- Other requests process in parallel

#### 3. Semaphore Acquisition
```
async with self.semaphore:  # asyncio.Semaphore
    ├── Acquires permit (may await)
    ├── Limits concurrent requests
    └── Auto-releases on exit
```

**Concurrency Control**:
- Maximum `max_concurrent_requests` in flight
- Queues excess requests automatically
- Fair ordering (FIFO) for waiters

#### 4. Async Generation Processing
```
await generation_engine.generate_output_async(generation_request)
├── _convert_to_llm_call_request() → synchronous transform
│
├── await _execute_llm_call_async(llm_call_request)
│   ├── await llm_handler.process_call_request_async()
│   │   ├── provider.convert_request() → sync transform
│   │   └── AsyncRetrying loop
│   │       └── await provider._invoke_async_impl()
│   │           └── await async_client.responses.create()
│   │
│   └── _build_generation_result() → sync transform
│
└── Returns GenerationResult
```

**Async Chain**:
- Each await point allows context switching
- HTTP call uses `httpx` async client
- Retry loop is async-aware

#### 5. Context Manager Cleanup
```
# Still within semaphore context:
├── metrics.mark_rcv() if success
├── metrics.unmark_sent() if failure
└── _after_response(result)
# Semaphore auto-released here
```

**Resource Management**:
- Semaphore released even on exception
- Metrics updated before release
- Ensures accurate concurrency tracking

### Parallel Execution Pattern

#### Multiple Concurrent Requests
```python
# User code pattern:
tasks = [
    service.execute_generation_async(req1),
    service.execute_generation_async(req2),
    service.execute_generation_async(req3)
]
results = await asyncio.gather(*tasks)
```

**Internal Behavior**:
```
Event Loop
├── Task 1: Waiting on RPM gate
├── Task 2: Waiting on semaphore
├── Task 3: Active API call
├── Task 4: Processing response
└── Task 5: Waiting on TPM gate
```

**Coordination Points**:
1. **RPM/TPM Gates**: Shared sliding windows
2. **Semaphore**: Shared concurrency limit
3. **Metrics**: Thread-safe shared state
4. **HTTP Client**: Connection pooling

### Async-Specific Error Handling

#### Cancellation Handling
```
try:
    await long_operation()
except asyncio.CancelledError:
    # Cleanup in rate gates:
    async with self._lock:
        self._waiters_count -= 1
    raise  # Re-raise to propagate
```

#### Timeout Handling
```
# User can wrap with timeout:
try:
    async with asyncio.timeout(30):
        result = await service.execute_generation_async(req)
except asyncio.TimeoutError:
    # Request cancelled, resources cleaned up
```

### State Synchronization

#### Shared State Access
```
# Thread-safe operations (no await):
metrics.mark_sent(trace_id)     # Lock-protected
metrics.rpm()                    # Lock-protected
usage_stats.update()             # Atomic operation

# Async coordination:
async with gate._lock:           # AsyncIO lock
    gate._waiters_count += 1     # Protected increment
```

**Design Principle**:
- Synchronous operations for shared state
- Async only for I/O and waiting
- Minimal time holding locks

### Performance Characteristics

#### Advantages Over Sync
1. **Non-blocking waits**: Thread continues during rate limiting
2. **Concurrent requests**: Multiple API calls in flight
3. **Better resource usage**: One thread handles many requests
4. **Scalability**: Handles thousands of concurrent requests

#### Bottlenecks
1. **Semaphore limit**: Max concurrent bounded
2. **Rate limits**: Still apply across all tasks
3. **Lock contention**: Brief during metric updates
4. **Event loop**: Single-threaded coordination

### Observable Differences from Sync

#### Timing
- Request ordering may differ from submission order
- Completion order depends on API latency
- Rate limit waits overlap between requests

#### Resource Usage
- Lower memory (fewer threads)
- Higher event loop CPU usage
- Shared HTTP connection pool

#### Error Propagation
- Exceptions in one task don't affect others
- `gather()` can return mixed success/failure
- Cancellation cascades through await chain

### Why Async Design

1. **Web Service Integration**: Natural fit for async frameworks (FastAPI, aiohttp)
2. **Batch Processing**: Efficient for parallel operations
3. **Rate Limit Efficiency**: Multiple requests coordinate waits
4. **Resource Efficiency**: Single thread handles many requests
5. **Modern Python**: Leverages async/await ecosystem

### Implementation Details

**Async Provider Clients**:
```python
# In provider initialization:
self.async_client = AsyncOpenAI(api_key=key)  # Separate client
# Not shared with sync client - different connection pools
```

**Async Lock vs Threading Lock**:
```python
# Async (for coroutines):
self._lock = asyncio.Lock()
async with self._lock:
    # Critical section

# Threading (for metrics):
self._lock = threading.Lock()
with self._lock:
    # Critical section
```

**Event Loop Assumptions**:
- Expects single event loop per thread
- Not thread-safe across different loops
- User must ensure proper loop management