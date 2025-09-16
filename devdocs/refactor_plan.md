# Refactor Plan: Full Migration to Responses API

## Executive Summary
Complete replacement of Chat Completions API with Responses API as the sole interface for LLM operations. Based on OpenAI's official migration guide, the Responses API provides:
- **3% better performance** on SWE-bench with same prompts
- **40-80% better cache utilization** resulting in lower costs
- **Native agentic capabilities** with built-in tools (web search, file search, code interpreter)
- **Stateful context management** with `store: true` and `previous_response_id`

## Migration Philosophy
**No backward compatibility. Clean break. Better future.**

## Key Benefits from Official Documentation
- **Better Performance**: 3% improvement in model intelligence
- **Lower Costs**: 40-80% improvement in cache utilization
- **Agentic by Default**: Multiple tool calls in single request
- **Stateful Context**: Automatic context preservation with `store: true`
- **Flexible Inputs**: String or messages array, separate instructions
- **Future-Proof**: Designed for upcoming models

## Core Architecture Changes

## Phase 1: Complete Schema Replacement

### 1.1 New Request Schemas (Based on Official API)
**File**: `llmservice/schemas.py`

```python
@dataclass
class LLMCallRequest:
    """Responses API request format matching official spec"""
    model_name: str
    input: Union[str, List[Dict]]  # String OR messages array for compatibility
    instructions: Optional[str] = None  # System-level guidance (replaces system role)
    previous_response_id: Optional[str] = None  # For CoT chaining
    store: bool = True  # Enable stateful context by default
    
    # GPT-5 specific parameters (from earlier docs)
    reasoning: Optional[Dict[str, str]] = None  # {"effort": "medium"}
    text: Optional[Dict[str, str]] = None  # {"verbosity": "medium", "format": {...}}
    
    # Tools (native and custom)
    tools: Optional[List[Dict]] = None  # Including native tools like web_search
    tool_choice: Optional[Dict] = None  # allowed_tools support
    
    # Standard parameters
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    
    # For ZDR compliance
    include: Optional[List[str]] = None  # ["reasoning.encrypted_content"]

@dataclass  
class GenerationRequest:
    """Simplified for Responses API with official patterns"""
    model: str
    input: Union[str, List[Dict]]  # Flexible input
    instructions: Optional[str] = None  # Cleaner than system messages
    previous_response_id: Optional[str] = None
    store: bool = True  # Stateful by default
    
    # Reasoning and output control
    reasoning: Dict[str, str] = field(default_factory=lambda: {"effort": "medium"})
    text: Dict[str, str] = field(default_factory=lambda: {"verbosity": "medium"})
    
    # Pipeline configuration
    pipeline: Optional[List[Dict]] = None
```

### 1.2 New Response Schemas (Items-based)
```python
@dataclass
class Item:
    """Base class for Responses API Items"""
    id: str
    type: Literal["message", "reasoning", "function_call", "function_call_output"]
    
@dataclass
class MessageItem(Item):
    """Message item in response"""
    type: Literal["message"] = "message"
    role: str = "assistant"
    content: List[Dict]  # [{"type": "output_text", "text": "..."}]
    status: str = "completed"
    
@dataclass
class ReasoningItem(Item):
    """Reasoning item (for reasoning models)"""
    type: Literal["reasoning"] = "reasoning"
    content: List[str]  # Reasoning steps
    summary: List[str]  # Reasoning summary
    encrypted_content: Optional[str] = None  # For ZDR compliance

@dataclass
class GenerationResult:
    """Responses API result with Items"""
    id: str  # Response ID for chaining
    object: Literal["response"] = "response"
    created_at: int
    model: str
    
    # Items-based output (not choices!)
    output: List[Item]  # Array of Items
    output_text: Optional[str]  # Helper property
    
    # Usage tracking (official format)
    usage: Dict[str, int]  # input_tokens, output_tokens, reasoning_tokens
    
    # Costs (calculated)
    total_cost: float
    reasoning_cost: float
    
    # Pipeline additions
    pipeline_results: List[PipelineStepResult] = field(default_factory=list)
    
    # For chaining
    stored: bool = True  # Whether this response was stored
```

## Phase 2: Single Provider Implementation

### 2.1 Replace ALL Providers with ResponsesProvider
**File**: `llmservice/providers/responses_provider.py`

```python
class ResponsesProvider(BaseLLMProvider):
    """The ONLY provider - Responses API for everything"""
    
    def __init__(self, model_name: str, logger: Optional[logging.Logger] = None):
        self.client = OpenAI()  # Responses API client
        self.model_name = model_name
        self.logger = logger
    
    def convert_request(self, request: LLMCallRequest) -> Dict:
        """Direct mapping to Responses API"""
        return {
            "model": request.model_name,
            "input": request.input,
            "reasoning": {"effort": request.reasoning_effort},
            "text": {"verbosity": request.verbosity},
            "previous_response_id": request.previous_response_id,
            "tools": request.tools,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens
        }
    
    def _invoke_impl(self, payload: Dict) -> Tuple[Any, bool, Optional[ErrorType]]:
        """Single implementation path"""
        try:
            response = self.client.responses.create(**payload)
            return response, True, None
        except Exception as e:
            return None, False, self._classify_error(e)
```

### 2.2 Delete Old Providers
**Actions**:
- DELETE `llmservice/providers/openai_provider.py`
- DELETE `llmservice/providers/ollama_provider.py` 
- DELETE `llmservice/providers/claude_provider.py`
- DELETE all `old_*.py` files

## Phase 3: Simplified LLMHandler

### 3.1 Remove Provider Detection
**File**: `llmservice/llm_handler.py`

```python
class LLMHandler:
    """Simplified handler - Responses API only"""
    
    def __init__(self, model_name: str, logger: Optional[logging.Logger] = None):
        self.model_name = model_name
        self.logger = logger
        self.provider = ResponsesProvider(model_name, logger)
        # NO provider detection, NO provider switching
    
    def process_call_request(self, request: LLMCallRequest) -> InvokeResponseData:
        """Single path execution"""
        payload = self.provider.convert_request(request)
        return self._execute_with_retry(payload)
    
    # REMOVED: change_model, _detect_provider, provider registry
```

## Phase 4: Streamlined Generation Engine

### 4.1 Remove Dual-Path Logic
**File**: `llmservice/generation_engine.py`

```python
class GenerationEngine:
    """Responses API native engine"""
    
    async def generate_output_async(self, request: GenerationRequest) -> GenerationResult:
        """Single async implementation"""
        llm_request = LLMCallRequest(
            model_name=request.model,
            input=request.input,
            reasoning_effort=request.reasoning["effort"],
            verbosity=request.text["verbosity"],
            previous_response_id=request.previous_response_id
        )
        
        response = await self.llm_handler.process_call_async(llm_request)
        
        return GenerationResult(
            success=response.success,
            output_text=response.response.output_text,
            reasoning_text=response.response.reasoning_text,
            response_id=response.response.response_id,
            # ... other fields
        )
    
    # REMOVED: generate_output sync method - async only
```

## Phase 5: CoT-Native Pipeline

### 5.1 Pipeline with Automatic CoT Passing
```python
class GenerationEngine:
    async def execute_pipeline(self, result: GenerationResult, 
                              pipeline_config: List[Dict]) -> GenerationResult:
        """Every step gets previous reasoning"""
        
        current_response_id = result.response_id
        current_content = result.output_text
        
        for step in pipeline_config:
            step_result = await self._execute_step(
                content=current_content,
                response_id=current_response_id,  # Always passed
                **step
            )
            
            # Update for next step
            current_content = step_result.output_text
            current_response_id = step_result.response_id
```

## Phase 6: Breaking Changes (Embrace Them!)

### 6.1 **API Contract Changes** ✅
```python
# OLD (Remove completely)
service.generate(
    prompt="Hello",
    messages=[{"role": "user", "content": "Hello"}],
    model="gpt-4"
)

# NEW (Only way)
service.generate(
    input="Hello",
    model="gpt-5",
    reasoning_effort="low"
)
```

### 6.2 **Response Access Changes** ✅
```python
# OLD (Remove)
result.content
result.choices[0].message

# NEW (Only)
result.output_text
result.reasoning_text
```

### 6.3 **Cost Structure Changes** ✅
```python
# NEW cost tracking
@dataclass
class UsageStats:
    total_requests: int
    total_tokens: int
    reasoning_tokens: int  # New category
    total_cost: float
    reasoning_cost: float  # Separate tracking
```

## Phase 7: Clean Deletions

### Files to DELETE
```
llmservice/
├── old_llm_handler.py          ❌ DELETE
├── old2_llm_handler.py         ❌ DELETE  
├── old_generation_engine.py    ❌ DELETE
├── old_base_servic.py          ❌ DELETE
├── providers/
│   ├── openai_provider.py      ❌ DELETE
│   ├── ollama_provider.py      ❌ DELETE
│   └── claude_provider.py      ❌ DELETE
```

### Code to REMOVE
- All message formatting logic
- All role-based prompt construction
- All provider detection code
- All Chat Completions references
- All sync wrappers (async only)
- All backward compatibility checks

## Phase 8: New Features to ADD

### 8.1 Native Tools Integration
```python
NATIVE_TOOLS = {
    "web_search": {"type": "web_search"},
    "file_search": {"type": "file_search"},
    "code_interpreter": {"type": "code_interpreter"},
    "computer_use": {"type": "computer_use"},
    "image_generation": {"type": "image_generation"},
    "mcp": {"type": "mcp", "server_label": "..."}
}

class ToolManager:
    """Manage native and custom tools"""
    def use_native_tools(self, tool_names: List[str]):
        return [NATIVE_TOOLS[name] for name in tool_names]
```

### 8.2 Stateful Context Management
```python
class ConversationContext:
    """Automatic context management with store=true"""
    def __init__(self, store_by_default: bool = True):
        self.last_response_id: Optional[str] = None
        self.store = store_by_default
        self.conversation_chain: List[str] = []  # Track response IDs
    
    async def generate(self, input: str, **kwargs):
        result = await client.responses.create(
            input=input,
            previous_response_id=self.last_response_id,
            store=self.store,
            **kwargs
        )
        self.last_response_id = result.id
        self.conversation_chain.append(result.id)
        return result
```

### 8.3 Encrypted Reasoning for ZDR
```python
class ZDRCompliantEngine:
    """Zero Data Retention compliant engine"""
    def __init__(self):
        self.store = False  # Never store
        self.include = ["reasoning.encrypted_content"]
    
    async def generate(self, input: str, encrypted_reasoning: Optional[str] = None):
        return await client.responses.create(
            input=input,
            store=False,
            include=["reasoning.encrypted_content"],
            # Pass encrypted reasoning from previous turn
            input=[{"type": "reasoning", "encrypted_content": encrypted_reasoning}] if encrypted_reasoning else input
        )
```

### 8.4 Structured Outputs with text.format
```python
def create_structured_request(input: str, schema: Dict):
    """Use text.format for structured outputs"""
    return {
        "input": input,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "response",
                "strict": True,
                "schema": schema
            }
        }
    }
```

## Phase 9: Migration Strategy (No Compatibility!)

### Step 1: Branch and Break (Day 1)
- Create `responses-api-only` branch
- Delete all old code immediately
- No feature flags, no gradual rollout

### Step 2: Rewrite Core (Days 2-5)
- Implement new schemas
- Implement ResponsesProvider
- Rewrite Generation Engine
- Update all pipelines

### Step 3: Update Examples (Days 6-7)
- Rewrite all examples for new API
- Remove all old patterns
- Add new Responses API examples

### Step 4: Testing (Days 8-10)
- New test suite (no regression tests needed!)
- Focus on Responses API features
- Test CoT persistence
- Test reasoning analytics

### Step 5: Documentation (Days 11-12)
- Complete rewrite of README
- New API reference
- Migration guide for users
- Remove all old documentation

### Step 6: Release (Day 13)
- Version 1.0.0 (major version bump)
- Clear breaking change notice
- No deprecation period

## Performance Targets (Based on Official Benchmarks)

### Expected Improvements (From OpenAI's Internal Tests)
- **3% better performance** on SWE-bench evaluations
- **40-80% better cache utilization** (cost reduction)
- **50% token reduction** with CoT reuse (reasoning models)
- **Lower latency** from reduced reasoning regeneration
- **Zero** legacy code overhead

### New Capabilities (Official Features)
- **Native tools**: web_search, file_search, code_interpreter, computer_use, image_generation
- **Stateful context**: Automatic with `store: true`
- **Flexible inputs**: String or messages array
- **Instructions**: Cleaner than system messages
- **Items-based output**: Better than choices array
- **Encrypted reasoning**: For ZDR compliance

## Success Metrics

### Technical
- [ ] 100% Responses API usage
- [ ] Zero Chat Completions code remaining
- [ ] All tests passing with new API
- [ ] Response cache hit rate > 30%

### Business
- [ ] Cost per request reduced by 40%
- [ ] Average latency reduced by 30%
- [ ] Token usage reduced by 50%
- [ ] Zero backward compatibility debt

## Timeline (Aggressive)

- **Days 1-5**: Core implementation
- **Days 6-7**: Examples update  
- **Days 8-10**: Testing
- **Days 11-12**: Documentation
- **Day 13**: Release

**Total: 2 weeks** (vs 5 weeks with compatibility)

## Post-Migration Architecture

### Clean Structure
```
llmservice/
├── schemas.py          # Responses API only schemas
├── handler.py          # Single handler, no detection
├── provider.py         # Single Responses provider
├── engine.py           # CoT-native engine
├── pipeline.py         # CoT-aware pipelines
├── cache.py            # Response ID cache
├── metrics.py          # Reasoning analytics
└── tools.py            # Custom tool utilities
```

### New Paradigms
1. **Input strings, not messages**
2. **Response IDs are mandatory**
3. **Reasoning is first-class**
4. **Async-only operations**
5. **CoT reuse by default**

## Risks (Acceptable!)

### What We're Breaking
1. ✅ All existing client code
2. ✅ All existing tests
3. ✅ All existing documentation
4. ✅ All existing examples

### What We're Gaining
1. Cleaner codebase (-50% LOC)
2. Better performance (see targets)
3. Lower costs (reasoning reuse)
4. Simpler mental model
5. Future-proof architecture

## Communication Plan

### For Users
```markdown
# LLMService 1.0 - Complete Responses API Migration

This is a BREAKING CHANGE. LLMService now uses OpenAI's Responses API exclusively.

## What Changed
- Everything. This is a complete rewrite.
- No backward compatibility with 0.x versions.
- Responses API only (GPT-5 optimized).

## Why
- 50% token reduction
- 40% lower latency  
- Native reasoning support
- Cleaner, simpler API

## Migration
See migration_guide.md for updating your code.
```

## Key API Differences (From Official Guide)

### Messages vs Items
| Chat Completions | Responses API |
|-----------------|---------------|
| `messages` array | `input` (string or array) + `instructions` |
| `choices[0].message.content` | `output_text` helper |
| Multiple choices with `n` param | Single generation only |
| Messages with mixed concerns | Distinct Item types |

### Function Definitions
| Chat Completions | Responses API |
|-----------------|---------------|
| External tagging | Internal tagging |
| Non-strict by default | Strict by default |
| `response_format` | `text.format` |
| Manual tool implementation | Native tools available |

### Context Management
| Chat Completions | Responses API |
|-----------------|---------------|
| Manual state management | `store: true` by default |
| Pass full history | Use `previous_response_id` |
| No reasoning persistence | Reasoning Items preserved |
| Stateless only | Stateful or encrypted stateless |

## The Bottom Line

**No compromise. No compatibility. Just better.**

By removing backward compatibility and adopting Responses API fully:
- **2 weeks instead of 5 weeks** implementation
- **50% less code to maintain** (single API path)
- **40-80% cost reduction** from cache utilization
- **3% better intelligence** on same prompts
- **Native agentic capabilities** out of the box
- **Future-proof** for upcoming models

This is the right choice for a library at 0.2.7 moving to 1.0.0, especially since:
- OpenAI recommends Responses API for all new projects
- Chat Completions will continue but won't get new features
- Assistants API is being deprecated (sunset August 2026)