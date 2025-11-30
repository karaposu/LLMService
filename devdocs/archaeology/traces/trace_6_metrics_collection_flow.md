# Trace 6: Metrics Collection Flow

## Interface: `MetricsRecorder` & `UsageStats`

### Entry Points
- **MetricsRecorder**: Real-time sliding window metrics
- **UsageStats**: Aggregated operation statistics
- **Locations**: `llmservice/live_metrics.py`, `llmservice/telemetry.py`

### Metrics Architecture

#### Two-Tier System
```
BaseLLMService
├── MetricsRecorder (real-time)
│   ├── Sliding window metrics (RPM/TPM)
│   ├── Request/response correlation
│   └── Cost accumulation
│
└── UsageStats (aggregated)
    ├── Per-operation breakdowns
    ├── Token usage summaries
    └── Cost tracking by category
```

### MetricsRecorder Flow

#### 1. Request Marking
```
mark_sent(req_id)
├── now = time.time()
├── with self._lock:
│   ├── self.total_sent += 1
│   ├── self.sent_ts.append(now)
│   ├── self.sent_ids.append(req_id)
│   └── self._trim_times(sent_ts, now, window)
```

**Data Structure Updates**:
```python
Before: sent_ts = [t-50, t-40, t-30]
        sent_ids = [101, 102, 103]
        total_sent = 3

After:  sent_ts = [t-50, t-40, t-30, t-0]
        sent_ids = [101, 102, 103, 104]
        total_sent = 4
```

#### 2. Response Marking
```
mark_rcv(req_id, tokens=150, cost=0.001)
├── now = time.time()
├── with self._lock:
│   ├── self.total_rcv += 1
│   ├── self.total_cost += cost
│   ├── self.rcv_ts.append(now)
│   ├── self.rcv_ids.append(req_id)
│   ├── self.tok_ts.append((now, tokens))
│   ├── self._trim_times(rcv_ts, now, window)
│   └── self._trim_tokens(now)
```

**Triple Recording**:
1. Response timestamp for RePM (responses per minute)
2. Token count for TPM (tokens per minute)
3. Cost accumulation for spend tracking

#### 3. Window Maintenance
```
_trim_times(deque, now, window)
├── cutoff = now - window
├── while deque and deque[0] < cutoff:
│   └── deque.popleft()
```

**Automatic Cleanup**:
- Old entries removed on every operation
- Prevents unbounded memory growth
- O(expired_entries) complexity

#### 4. Rate Calculations
```
rpm() → float
├── with self._lock:
│   ├── now = time.time()
│   ├── self._trim_times(sent_ts, now, window)
│   └── return len(sent_ts) * 60 / window

tpm() → float
├── with self._lock:
│   ├── now = time.time()
│   ├── self._trim_tokens(now)
│   ├── total = sum(tok for _, tok in tok_ts)
│   └── return total * 60 / window
```

**Real-Time Metrics**:
- Always current when queried
- No background threads needed
- Lock ensures consistency

#### 5. Snapshot Generation
```
snapshot() → StatsSnapshot
├── now = time.time()
├── with self._lock:  # Single lock for atomicity
│   └── return StatsSnapshot(
│       total_sent=self.total_sent,
│       total_rcv=self.total_rcv,
│       rpm=self._rpm_unlocked(now),
│       repm=self._repm_unlocked(now),
│       tpm=self._tpm_unlocked(now),
│       cost=self.total_cost
│   )
```

**Atomic Read**:
- All metrics from same point in time
- No partial updates visible
- Used for monitoring/logging

### UsageStats Flow

#### 1. Operation Recording
```
UsageStats.update(usage_dict, operation_name="chat")
├── with self._lock:
│   ├── op_stats = self._ensure_operation(operation_name)
│   ├── op_stats["count"] += 1
│   ├── op_stats["input_tokens"] += usage["input_tokens"]
│   ├── op_stats["output_tokens"] += usage["output_tokens"]
│   ├── op_stats["total_tokens"] += usage["total_tokens"]
│   ├── op_stats["input_cost"] += usage["input_cost"]
│   ├── op_stats["output_cost"] += usage["output_cost"]
│   └── op_stats["total_cost"] += usage["total_cost"]
```

**Per-Operation Tracking**:
```python
operations = {
    "chat": {
        "count": 150,
        "input_tokens": 15000,
        "output_tokens": 30000,
        "total_cost": 0.45
    },
    "summarize": {
        "count": 50,
        "input_tokens": 50000,
        "output_tokens": 5000,
        "total_cost": 0.55
    }
}
```

#### 2. Aggregation Queries
```
get_total_cost() → float
├── with self._lock:
│   └── return sum(op["total_cost"] for op in operations.values())

get_operation_stats(operation_name) → dict
├── with self._lock:
│   └── return operations.get(operation_name, default_stats())
```

### Correlation and Rollback

#### Request ID Tracking
```
# Correlation through request lifecycle:
mark_sent(req_id=12345)
    ↓ [Processing]
mark_rcv(req_id=12345, tokens=100, cost=0.01)

# IDs enable rollback:
unmark_sent(req_id=12345)  # If request never sent
unmark_rcv(req_id=12345)   # If response invalid
```

#### Rollback Mechanism
```
unmark_sent(req_id)
├── with self._lock:
│   ├── Find req_id in sent_ids
│   ├── Get index
│   ├── Remove from sent_ids[index]
│   ├── Remove from sent_ts[index]
│   └── self.total_sent -= 1
```

**Use Cases**:
- Rate limit hit before actual send
- Provider authentication failure
- Request validation error

### Telemetry Integration

#### Event Timestamps
```
EventTimestamps tracking:
├── generation_requested_at    # User call
├── generation_enqueued_at     # Pre-rate-limit
├── generation_dequeued_at     # Post-rate-limit
├── llm_request_sent_at       # Provider call
├── llm_response_received_at  # Provider response
├── response_returned_at      # User return
└── processing_complete_at    # Final cleanup
```

**Latency Calculation**:
```python
queue_time = dequeued_at - enqueued_at
llm_time = response_received_at - request_sent_at
total_time = processing_complete_at - requested_at
```

#### Backoff Statistics
```
BackoffStats collection:
├── rpm_gated: bool
├── rpm_wait_loops: int
├── rpm_waited_ms: int
├── tpm_gated: bool
├── tpm_wait_loops: int
├── tpm_waited_ms: int
└── retry_count: int
```

### Memory Management

#### Bounded Data Structures
```
Window = 60 seconds
Max RPM = 100
Max entries in sent_ts = 100

Max TPM = 100000
Avg tokens per request = 500
Max entries in tok_ts = 200

Total memory < 1KB per window
```

#### Cleanup Triggers
```
Cleanup happens on:
├── Every mark_sent()
├── Every mark_rcv()
├── Every rate calculation
└── Never requires manual cleanup
```

### Thread Safety

#### Lock Hierarchy
```
MetricsRecorder._lock (threading.Lock)
├── Protects all deques
├── Protects all counters
├── Brief hold time (<1ms)

UsageStats._lock (threading.Lock)
├── Protects operations dict
├── Independent of metrics lock
└── No deadlock possible
```

#### Atomic Operations
```python
# All updates atomic:
with self._lock:
    # Multiple updates appear instantaneous
    self.total_sent += 1
    self.sent_ts.append(now)
    self.sent_ids.append(req_id)
```

### Observable Outputs

#### Log Integration
```python
# Optional file logger:
logger = attach_file_handler(
    recorder=metrics,
    path="/var/log/llm_metrics.log"
)

# Writes structured logs:
2024-01-15 10:30:45 RPM: 25.3, TPM: 4532, Cost: $1.23
2024-01-15 10:30:46 Request sent: req_12345
2024-01-15 10:30:47 Response received: req_12345 (150 tokens)
```

#### Monitoring Integration
```python
# Snapshot for monitoring systems:
stats = metrics.snapshot()
prometheus.set_gauge('llm_rpm', stats.rpm)
prometheus.set_gauge('llm_tpm', stats.tpm)
prometheus.set_counter('llm_total_cost', stats.cost)
```

### Cost Tracking

#### Granular Cost Recording
```
Per Request:
├── Input tokens * input rate
├── Output tokens * output rate
├── Reasoning tokens * reasoning rate
└── Total cost

Per Operation:
├── Sum of request costs
├── Average cost per request
└── Cost trend over time
```

#### Cost Optimization Insights
```python
# Identify expensive operations:
for op, stats in usage_stats.get_all():
    avg_cost = stats["total_cost"] / stats["count"]
    if avg_cost > threshold:
        log.warning(f"Operation {op} costs ${avg_cost}/request")
```

### Why This Design

1. **Real-Time Metrics**: Instant visibility into rates
2. **No External Dependencies**: Pure Python implementation
3. **Thread-Safe**: Safe for concurrent access
4. **Memory Efficient**: Bounded data structures
5. **Rollback Support**: Handles failed requests gracefully
6. **Operation Tracking**: Business-level metrics

### Performance Characteristics

**CPU Impact**:
- Lock acquisition: ~0.01ms
- Deque operations: O(1)
- Window trim: O(expired_entries)
- Negligible overhead per request

**Memory Impact**:
- ~1KB per 60-second window
- No memory leaks
- Automatic cleanup

**Accuracy**:
- Exact counts (not sampled)
- Microsecond timestamp precision
- No metric loss on crash (in-memory only)