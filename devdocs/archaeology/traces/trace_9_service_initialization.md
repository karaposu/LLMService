# Trace 9: Service Initialization Flow

## Interface: `BaseLLMService.__init__()`

### Entry Point
- **Location**: `llmservice/base_service.py:34`
- **Called by**: User service classes (e.g., `MyLLMService`)
- **Purpose**: Initialize all subsystems

### Initialization Sequence

#### 1. Core Components
```
BaseLLMService.__init__(default_model_name="gpt-4o-mini", ...)
├── self.default_model_name = default_model_name
├── self.show_logs = show_logs
└── self.show_usage_cost_in_logs = show_usage_cost_in_logs
```

#### 2. Rate Limiting Setup
```
set_rate_limits(max_rpm, max_tpm, window_seconds=60)
├── self.max_rpm = max_rpm
├── self.max_tpm = max_tpm
├── self.window_seconds = window_seconds
│
├── Create MetricsRecorder
│   └── self.metrics = MetricsRecorder(
│       window=window_seconds,
│       max_rpm=max_rpm,
│       max_tpm=max_tpm
│   )
│
├── Create Rate Gates
│   ├── self._rpm_gate = RpmGate(window_seconds)
│   └── self._tpm_gate = TpmGate(window_seconds)
```

**Default Configuration**:
```python
max_rpm = None  # No limit
max_tpm = None  # No limit
window_seconds = 60  # 1 minute sliding window
```

#### 3. Concurrency Control
```
set_concurrency(max_concurrent_requests=5)
├── self.max_concurrent_requests = max_concurrent_requests
└── self.semaphore = asyncio.Semaphore(max_concurrent_requests)
```

**Semaphore Behavior**:
- Limits parallel async requests
- No effect on sync requests
- Fair FIFO ordering

#### 4. Engine Initialization
```
self.generation_engine = GenerationEngine(
    model_name=default_model_name,
    config={}  # Optional config
)
├── Creates LLMHandler
│   ├── handler = LLMHandler(model_name)
│   │   ├── Selects provider
│   │   └── Initializes clients
│   └── self.llm_handler = handler
```

#### 5. Telemetry Setup
```
self.usage_stats = UsageStats()
├── self.operations = {}  # Empty operation dict
└── self._lock = threading.Lock()
```

### Dependency Chain

#### Initialization Order Matters
```
1. Model name (needed by engine)
   ↓
2. Metrics recorder (needed by gates)
   ↓
3. Rate gates (need metrics)
   ↓
4. Generation engine (needs model)
   ↓
5. Usage stats (independent)
```

#### Provider Client Initialization
```
LLMHandler.__init__(model_name)
├── ResponsesAPIProvider(model_name)
│   ├── self.client = OpenAI(api_key=key)
│   │   ├── HTTP client setup
│   │   ├── Connection pooling
│   │   └── Retry configuration
│   │
│   └── self.async_client = AsyncOpenAI(api_key=key)
│       └── Separate async HTTP client
```

**Client Configuration**:
```python
timeout = httpx.Timeout(600.0, connect=5.0)
max_retries = 0  # We handle retries
```

### Configuration Methods

#### Runtime Reconfiguration
```python
# Can be called after init:
service.set_rate_limits(max_rpm=30, max_tpm=5000)
├── Updates metrics.max_rpm
├── Updates metrics.max_tpm
└── Takes effect immediately

service.set_concurrency(10)
├── Creates new semaphore
└── Affects new requests only
```

#### Model Switching
```python
# Happens automatically on request:
request = GenerationRequest(model="gpt-5")
├── Engine detects model change
├── Handler creates new provider
└── Lazy initialization
```

### Resource Allocation

#### Memory Footprint
```
Per service instance:
├── MetricsRecorder: ~2KB (deques)
├── Rate gates: ~1KB (state)
├── Semaphore: ~100B
├── Engine/Handler: ~5KB
├── Provider clients: ~50KB (connection pools)
└── Total: ~60KB baseline
```

#### Thread Resources
```
Sync operation:
└── Uses calling thread only

Async operation:
├── Event loop required
├── No additional threads
└── Coroutines share loop
```

### Error Handling During Init

#### API Key Validation
```python
# Lazy validation - not checked during init
# First request triggers validation:
try:
    client.responses.create(...)
except AuthenticationError:
    # Invalid API key detected
```

#### Missing Dependencies
```python
try:
    from openai import OpenAI
except ImportError:
    raise ImportError("pip install openai required")
```

### Observable State After Init

#### Ready State
```python
service.__dict__ = {
    'default_model_name': 'gpt-4o-mini',
    'metrics': <MetricsRecorder>,
    '_rpm_gate': <RpmGate>,
    '_tpm_gate': <TpmGate>,
    'semaphore': <Semaphore(5)>,
    'generation_engine': <GenerationEngine>,
    'usage_stats': <UsageStats>,
    'max_rpm': None,
    'max_tpm': None,
    'max_concurrent_requests': 5
}
```

#### Metrics State
```python
metrics.__dict__ = {
    'window': 60,
    'sent_ts': deque([]),
    'rcv_ts': deque([]),
    'tok_ts': deque([]),
    'total_sent': 0,
    'total_rcv': 0,
    'total_cost': 0.0
}
```

### Why This Design

1. **Lazy Provider Init**: Only create when needed
2. **Configurable Limits**: Tune for use case
3. **Separate Clients**: Sync/async isolation
4. **Minimal Upfront Cost**: Fast initialization
5. **Runtime Flexibility**: Reconfigure without restart

### Common Patterns

#### Service Subclassing
```python
class MyLLMService(BaseLLMService):
    def __init__(self):
        super().__init__(
            default_model_name="gpt-4o-mini",
            max_rpm=30,
            max_tpm=10000
        )
        # Custom initialization
        self.custom_state = {}
```

#### Factory Pattern
```python
def create_service(env="prod"):
    if env == "prod":
        return BaseLLMService(max_rpm=100)
    else:
        return BaseLLMService(max_rpm=10)
```

### Cleanup

#### No Explicit Cleanup Needed
```
Resources auto-cleanup:
├── HTTP clients: Connection pool timeout
├── Deques: Garbage collected
├── Semaphores: Released on exit
└── No background threads to stop
```

#### Context Manager Support
```python
# Could be enhanced with:
class BaseLLMService:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cleanup()  # Close clients
```