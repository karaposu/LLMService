# Technical Concepts List

## Core Infrastructure

### 1. **Provider Abstraction Layer**
Abstract interface for swapping LLM providers (OpenAI, Claude, Ollama)

### 2. **Request/Response Pipeline**
Multi-layer transformation from user request to API call to result

### 3. **Dual Client Architecture**
Separate sync and async HTTP clients to prevent event loop pollution

## Rate Management

### 4. **Sliding Window Rate Limiting**
Time-based deques that auto-expire old entries for smooth throughput

### 5. **RPM (Requests Per Minute) Control**
Hard limit on request frequency with proactive blocking

### 6. **TPM (Tokens Per Minute) Control**
Token usage throttling based on sliding consumption window

### 7. **Semaphore-Based Concurrency**
Async concurrency limiter using asyncio.Semaphore

## Data Structures & State

### 8. **Compensating Transactions**
Rollback mechanism for metrics (unmark_sent, unmark_rcv)

### 9. **Request Correlation**
Trace IDs linking requests through all layers

### 10. **Deque-Based Metrics**
Bounded collections with O(1) append/pop operations

### 11. **Atomic Snapshots**
Thread-safe metric reads with single lock acquisition

## API Integration

### 12. **Structured Output via JSON Schema**
Pydantic models converted to JSON Schema for API enforcement

### 13. **CoT Response Chaining**
Stateful conversation via response_id linking

### 14. **Multimodal Support**
Base64 encoding for images and audio in requests

### 15. **Provider Payload Conversion**
Request transformation to provider-specific formats

## Error Handling & Resilience

### 16. **Exponential Backoff with Jitter**
Retry delays: 2^attempt + random() to prevent thundering herd

### 17. **Error Classification**
Enum-based error types (INSUFFICIENT_QUOTA, UNSUPPORTED_REGION, etc.)

### 18. **Selective Retry Logic**
Retry on 429/5xx, fail on 4xx errors

### 19. **Graceful Cancellation**
Async cleanup in finally blocks

## Observability

### 20. **Real-Time Metrics Collection**
In-memory sliding window metrics without persistence

### 21. **Per-Operation Usage Tracking**
Token/cost aggregation by operation name

### 22. **Attempt Recording**
Detailed timing for each retry attempt

### 23. **Backoff Statistics**
Wait time and loop count tracking

## Resource Management

### 24. **Connection Pooling**
HTTP client connection reuse (delegated to httpx)

### 25. **Automatic Memory Bounds**
Deques limited by time window, preventing unbounded growth

### 26. **Lock Hierarchy**
Separate locks for metrics vs usage stats, preventing deadlock

### 27. **Context Manager Integration**
Semaphore auto-release on scope exit

## Schema & Validation

### 28. **Pydantic Model Validation**
Runtime type checking for structured outputs

### 29. **Strict Mode Schema Enforcement**
API-level guarantee of schema compliance

### 30. **Field-Level Constraints**
Min/max values, regex patterns in schemas

## Async Patterns

### 31. **Async Generator Pattern**
For streaming responses (prepared but unused)

### 32. **Event Loop Isolation**
Sync operations never await, async never blocks

### 33. **Coroutine Coordination**
Multiple waiters tracked via _waiters_count

## Cost Management

### 34. **Model-Specific Pricing Tables**
Cost per million tokens by model

### 35. **Reasoning Token Tracking**
Separate cost calculation for CoT tokens

### 36. **Cumulative Cost Accumulation**
Running total across all requests

## Configuration & Initialization

### 37. **Lazy Provider Initialization**
Providers created only when model accessed

### 38. **Runtime Reconfiguration**
Rate limits adjustable without restart

### 39. **Environment Variable Loading**
API keys from .env via python-dotenv

## Data Transformation

### 40. **Request Field Mapping**
GenerationRequest.model → LLMCallRequest.model_name

### 41. **Response Extraction**
Provider-specific response → standardized format

### 42. **Usage Metadata Enrichment**
Raw tokens → tokens + costs + percentages

## Time Management

### 43. **Wall Clock Timestamps**
time.time() for all timing operations

### 44. **Window Expiry Calculation**
now - window_size for cutoff determination

### 45. **Request Latency Tracking**
End-to-end and per-stage timing

## Thread Safety

### 46. **Fine-Grained Locking**
Brief lock holds only during mutations

### 47. **Lock-Free Reads**
Where possible, immutable snapshots

### 48. **No Nested Locks**
Preventing deadlock by design

## Network & I/O

### 49. **Timeout Configuration**
600s default, 5s connect timeout

### 50. **HTTP Status Handling**
Mapping HTTP codes to error types

### 51. **Network Error Recovery**
Connection reset resilience

## Algorithms

### 52. **Sliding Window Trim**
O(expired_entries) cleanup algorithm

### 53. **Request Hash Computation**
For future deduplication support

### 54. **Circular Deque Management**
FIFO with automatic size limits