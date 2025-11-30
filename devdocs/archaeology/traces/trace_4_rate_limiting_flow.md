# Trace 4: Rate Limiting Flow

## Interface: `RpmGate.wait_if_rate_limited()` & `TpmGate.wait_if_token_limited()`

### Entry Points
- **Callers**: `BaseLLMService.execute_generation()` and async variant
- **Input**: `MetricsRecorder` instance with sliding window data
- **Locations**: `llmservice/gates.py:41` (RPM), `llmservice/gates.py:183` (TPM)

### Rate Limiting Architecture

#### Core Components
```
BaseLLMService
├── MetricsRecorder (shared state)
│   ├── sent_ts: deque[float]         # Request timestamps
│   ├── rcv_ts: deque[float]          # Response timestamps
│   ├── tok_ts: deque[(float, int)]   # Token usage timestamps
│   └── window: int (60 seconds)      # Sliding window size
│
├── RpmGate (request rate control)
│   ├── _window: float (60s)
│   ├── _waiters_count: int           # Waiting coroutines
│   └── _lock: asyncio.Lock           # Coordination
│
└── TpmGate (token rate control)
    ├── _window: float (60s)
    ├── _waiters_count: int
    └── _lock: asyncio.Lock
```

### RPM (Requests Per Minute) Flow

#### 1. Rate Check
```
wait_if_rate_limited(metrics)
├── while metrics.is_rpm_limited():
│   ├── metrics.rpm() → current RPM
│   │   ├── _trim_times(sent_ts, now)
│   │   │   └── Remove entries older than window
│   │   └── len(sent_ts) * 60 / window
│   │
│   └── Compare with max_rpm
│       └── Continue loop if over limit
```

**Sliding Window Calculation**:
```python
# Example with window=60s, max_rpm=30:
sent_ts = [t-55, t-45, t-30, t-20, t-10, t-5, t-2]
# After trim (remove > 60s old): 7 requests
current_rpm = 7 * (60/60) = 7 RPM
# If max_rpm=5, must wait
```

#### 2. Wait Time Calculation
```
_secs_until_refresh(sent_ts, window)
├── oldest = sent_ts[0]
├── elapsed = now - oldest
├── remaining = window - elapsed
└── return max(0.0, remaining)
```

**Example Calculation**:
```python
# oldest request at t-55s
# window = 60s
# wait_time = 60 - 55 = 5 seconds
# After 5s, oldest drops out of window
```

#### 3. Coordinated Waiting (Async)
```
async with self._lock:
    self._waiters_count += 1
    waiters = self._waiters_count

# Log if meaningful delay
if wait_ms > 5 and loop_count > self._last_logged_round:
    logging.warning("RPM ⏳ %d waiting | next window in %.2fs")

await asyncio.sleep(wait_for_s)

async with self._lock:
    self._waiters_count -= 1
```

**Multi-Coroutine Behavior**:
```
Time | Coroutine 1 | Coroutine 2 | Coroutine 3 | waiters_count
0s   | Check RPM   | -           | -           | 0
0s   | Start wait  | -           | -           | 1
0.1s | Waiting...  | Check RPM   | -           | 1
0.1s | Waiting...  | Start wait  | -           | 2
0.2s | Waiting...  | Waiting...  | Check RPM   | 2
0.2s | Waiting...  | Waiting...  | Start wait  | 3
5s   | Wake up     | Wake up     | Wake up     | 0
5s   | Proceed     | Check again | Check again | 0-2
```

### TPM (Tokens Per Minute) Flow

#### 1. Token Usage Tracking
```
# On response:
metrics.mark_rcv(request_id, tokens=150, cost=0.01)
├── tok_ts.append((now, 150))
└── Tuple stores timestamp and token count
```

#### 2. TPM Calculation
```
metrics.tpm()
├── _trim_tokens(now)
│   └── Remove entries older than window
├── sum(tok for _, tok in tok_ts)
└── total * 60 / window
```

**Example with Multiple Requests**:
```python
tok_ts = [
    (t-50, 100),  # 100 tokens 50s ago
    (t-30, 200),  # 200 tokens 30s ago
    (t-10, 150),  # 150 tokens 10s ago
]
total = 450 tokens
current_tpm = 450 * (60/60) = 450 TPM
```

#### 3. Token-Based Waiting
```
wait_if_token_limited(metrics)
├── while metrics.is_tpm_limited():
│   ├── Check current TPM vs max_tpm
│   ├── Calculate wait based on oldest token entry
│   └── Sleep until oldest expires from window
```

### Combined Rate Limiting

#### Execution Order
```
BaseLLMService.execute_generation()
├── 1. RPM Gate check/wait
├── 2. TPM Gate check/wait
├── 3. Mark request sent
├── 4. Process request
└── 5. Mark tokens used
```

**Why This Order**:
1. RPM first: Cheaper to check, fails fast
2. TPM second: More complex calculation
3. Mark sent: Updates RPM window
4. Mark tokens: Updates TPM window after success

#### Race Conditions Prevention
```
# Metrics updates are atomic:
with self._lock:  # threading.Lock
    self.sent_ts.append(now)
    self.total_sent += 1

# Gate checks are consistent:
with self._lock:
    self._trim_times(sent_ts, now)
    return len(sent_ts) * 60 / window
```

### Edge Cases and Behaviors

#### Burst Handling
```
# 10 rapid requests with max_rpm=6:
Request 1-6: Pass immediately
Request 7: Wait ~10s (until req 1 expires)
Request 8: Wait ~10s (until req 2 expires)
...continues spacing out
```

#### Window Rollover
```
# As time passes:
t=0:   [req1, req2, req3] → 3 in window
t=30:  [req1, req2, req3, req4] → 4 in window
t=61:  [req2, req3, req4] → 3 in window (req1 expired)
```

#### Concurrent Waiter Behavior
```
# Multiple coroutines hit limit:
All waiters wake simultaneously when window refreshes
First to recheck may proceed
Others may need to wait again
Fair ordering not guaranteed (race to recheck)
```

### Performance Implications

#### Memory Usage
```
sent_ts: O(max_rpm) - bounded by rate limit
tok_ts: O(max_tpm/avg_tokens) - bounded by token limit
Maximum entries = requests in 60s window
```

#### CPU Usage
```
Trim operation: O(n) where n = expired entries
RPM calculation: O(1) after trim
TPM calculation: O(m) where m = token entries
Lock contention: Brief, only during updates
```

#### Wait Time Distribution
```
Uniform arrivals → Exponential wait times
Burst arrivals → Linear wait spacing
Mixed pattern → Hybrid distribution
```

### Observable Metrics

#### Logged Information
```
"RPM ⏳ 3 waiting | next window in 4.5s | round #2"
- Number of concurrent waiters
- Time until window refresh
- Loop iteration (for debugging)
```

#### Backoff Statistics
```
GenerationResult includes:
- rpm_waited: bool (did we wait?)
- rpm_loops: int (how many check loops?)
- rpm_waited_ms: int (total wait time)
- Same for TPM
```

### Why This Design

1. **Sliding Window**: More accurate than fixed buckets
2. **Proactive Limiting**: Prevents 429 errors from provider
3. **Deque Structure**: Efficient append/pop operations
4. **Shared State**: All requests coordinate through same windows
5. **Async-Aware**: Non-blocking waits for async operations
6. **Configurable**: Can adjust window size and limits

### Configuration Examples

#### Conservative Setup
```python
service.set_rate_limits(
    max_rpm=10,      # Very low request rate
    max_tpm=1000     # Very low token rate
)
# Ensures never hit provider limits
```

#### Aggressive Setup
```python
service.set_rate_limits(
    max_rpm=100,     # High request rate
    max_tpm=100000   # High token rate
)
# Maximizes throughput, may hit provider limits
```

#### Balanced Setup
```python
service.set_rate_limits(
    max_rpm=30,      # Moderate request rate
    max_tpm=10000    # Moderate token rate
)
# Good balance of throughput and safety
```

### Implementation Details

**Deque Behavior**:
```python
# Append is O(1)
sent_ts.append(timestamp)

# Pop from left is O(1)
while sent_ts and sent_ts[0] < cutoff:
    sent_ts.popleft()
```

**Lock Granularity**:
```python
# Fine-grained locking:
with self._lock:
    # Only hold during mutation
    self._waiters_count += 1

# Not during sleep:
await asyncio.sleep(5)  # Lock released
```

**Time Source**:
```python
time.time()  # Monotonic wall clock
# Used consistently throughout
# No timezone issues
```