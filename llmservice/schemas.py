# schemas.py

from dataclasses import dataclass, field, fields
from typing import Any, Dict, Optional, Union, Literal , List
import pprint
from datetime import datetime, timezone, timedelta



import json

def indent_text(text, indent):
    indentation = ' ' * indent
    return '\n'.join(indentation + line for line in text.splitlines())





@dataclass
class InvocationAttempt:
    attempt_number:    int

    invoke_start_at:      datetime
    invoke_end_at:        datetime
    backoff_after_ms:  Optional[int] = None
    error_message:     Optional[str] = None


    def duration_ms(self) -> float:
        """Milliseconds spent in this invoke call."""
        return (self.invoke_end - self.invoke_start).total_seconds() * 1_000

    def backoff_ms(self) -> float:
        """Milliseconds of backoff after this attempt (0 if none)."""
        return self.backoff_after_ms.total_seconds() * 1_000 if self.backoff_after_ms else 0.0





from dataclasses import dataclass, field
from typing import Any, List, Optional

@dataclass
class InvokeResponseData:
    """
    Wrapper for a single LLM invoke call (sync or async),
    including all retry attempts and derived metrics.
    """
    success: bool
    response: Any
    attempts: List[InvocationAttempt] = field(default_factory=list)

    # Derived metrics, not passed in by caller
    total_duration_ms: float         = field(init=False)
    attempt_count: int               = field(init=False)
    total_backoff_ms: float          = field(init=False)
    last_error_message: Optional[str]= field(init=False)
    retried: bool                    = field(init=False)

    def __post_init__(self):
        self.attempt_count    = len(self.attempts)
        if self.attempts:
            start = self.attempts[0].invoke_start_at
            end   = self.attempts[-1].invoke_end_at
            self.total_duration_ms = (end - start).total_seconds() * 1_000
            self.total_backoff_ms  = sum(a.backoff_ms() for a in self.attempts)
            # last error only if the final attempt failed
            last = self.attempts[-1]
            self.last_error_message = last.error_message
        else:
            self.total_duration_ms = 0.0
            self.total_backoff_ms  = 0.0
            self.last_error_message = None
        
        self.retried = (self.attempt_count > 1)



@dataclass
class EventTimestamps:
    generation_requested_at:      datetime
    generation_enqueued_at:       Optional[datetime] = None
    generation_dequeued_at:       Optional[datetime] = None

    attempts:                     List[InvocationAttempt] = field(default_factory=list)

    semanticisolation_start_at:   Optional[datetime] = None
    semanticisolation_end_at:     Optional[datetime] = None

    converttodict_start_at:       Optional[datetime] = None
    converttodict_end_at:         Optional[datetime] = None

    extractvalue_start_at:        Optional[datetime] = None
    extractvalue_end_at:          Optional[datetime] = None

    stringmatchvalidation_start_at: Optional[datetime] = None
    stringmatchvalidation_end_at:   Optional[datetime] = None

    jsonload_start_at:            Optional[datetime] = None
    jsonload_end_at:              Optional[datetime] = None

    postprocessing_completed_at:  Optional[datetime] = None
    generation_completed_at:      Optional[datetime] = None

    def total_duration_ms(self) -> float:
        if self.generation_completed_at:
            return (self.generation_completed_at - self.generation_requested_at).total_seconds() * 1_000
        return 0.0

    def invoke_durations_ms(self) -> List[float]:
        return [a.duration_ms() for a in self.attempts]

    def total_backoff_ms(self) -> float:
        return sum(a.backoff_ms() for a in self.attempts)

    def postprocessing_duration_ms(self) -> float:
        if self.postprocessing_completed_at and self.attempts:
            last_end = self.attempts[-1].invoke_end_at
            return (self.postprocessing_completed_at - last_end).total_seconds() * 1_000
        return 0.0

    def to_dict(self) -> Dict[str, any]:
        data: Dict[str, any] = {
            "generation_requested_at":      self.generation_requested_at.isoformat(),
            "generation_enqueued_at":       self.generation_enqueued_at.isoformat() if self.generation_enqueued_at else None,
            "generation_dequeued_at":       self.generation_dequeued_at.isoformat() if self.generation_dequeued_at else None,
            "postprocessing_completed_at":  self.postprocessing_completed_at.isoformat() if self.postprocessing_completed_at else None,
            "generation_completed_at":      self.generation_completed_at.isoformat() if self.generation_completed_at else None,
            "attempts": [
                {
                    "n": a.attempt_number,
                    "invoke_start_at": a.invoke_start_at.isoformat(),
                    "invoke_end_at":   a.invoke_end_at.isoformat(),
                    "duration_ms":     a.duration_ms(),
                    "backoff_ms":      a.backoff_ms(),
                    "error_message":   a.error_message,
                }
                for a in self.attempts
            ],
            "total_duration_ms":          self.total_duration_ms(),
            "invoke_durations_ms":        self.invoke_durations_ms(),
            "total_backoff_ms":           self.total_backoff_ms(),
            "postprocessing_duration_ms": self.postprocessing_duration_ms(),
        }
        # include any explicit step times if present
        for attr in (
            "semanticisolation_start_at", "semanticisolation_end_at",
            "converttodict_start_at",     "converttodict_end_at",
            "extractvalue_start_at",      "extractvalue_end_at",
            "stringmatchvalidation_start_at","stringmatchvalidation_end_at",
            "jsonload_start_at",          "jsonload_end_at"
        ):
            ts = getattr(self, attr)
            if ts:
                data[attr] = ts.isoformat()
        return data





@dataclass
class GenerationRequest:
    # Provide either `formatted_prompt` OR both of `unformatted_prompt` and `data_for_placeholders`
    formatted_prompt: Optional[str] = None
    unformatted_prompt: Optional[str] = None
    data_for_placeholders: Optional[Dict[str, Any]] = None
    
    model: Optional[str] = None
    output_type: Literal["json", "str"] = "str"
    operation_name: Optional[str] = None
    request_id: Optional[Union[str, int]] = None
    number_of_retries: Optional[int] = None
    pipeline_config: List[Dict[str, Any]] = field(default_factory=list)
    fail_fallback_value: Optional[str] = None
    
    def __post_init__(self):
        has_formatted    = self.formatted_prompt is not None
        has_unformatted  = self.unformatted_prompt is not None
        has_placeholders = self.data_for_placeholders is not None

        # If a formatted_prompt is given, disallow the other two
        if has_formatted and (has_unformatted or has_placeholders):
            raise ValueError(
                "Use either `formatted_prompt` by itself, "
                "or both `unformatted_prompt` and `data_for_placeholders`, not both."
            )
        # If no formatted_prompt, require both unformatted_prompt and data_for_placeholders
        if not has_formatted:
            if not (has_unformatted and has_placeholders):
                raise ValueError(
                    "Either `formatted_prompt` must be set, "
                    "or both `unformatted_prompt` and `data_for_placeholders` must be provided."
                )






@dataclass
class PipelineStepResult:
    step_type: str
    success: bool
    content_before: Any
    content_after: Any
    error_message: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)




@dataclass
class GenerationResult:
    success: bool
    trace_id: str           
    request_id: Optional[Union[str, int]] = None
    content: Optional[Any] = None
    raw_content: Optional[str] = None  # Store initial LLM output
    operation_name: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    elapsed_time: Optional[float] = None
    error_message: Optional[str] = None
    model: Optional[str] = None
    formatted_prompt: Optional[str] = None
    unformatted_prompt: Optional[str] = None
    response_type: Optional[str] = None
    how_many_retries_run: Optional[int] = None
    pipeline_steps_results: List[PipelineStepResult] = field(default_factory=list)
    generation_request: Optional[GenerationRequest] = None
    rpm_at_the_beginning: Optional[int] = None
    rpm_at_the_end: Optional[int] = None
    tpm_at_the_beginning: Optional[int] = None
    tpm_at_the_end: Optional[int] = None

    # ← NEW: embed our structured timestamps

    timestamps: Optional[EventTimestamps] = None
    
    def __str__(self) -> str:
        lines = [
            f"▶️ GenerationResult:",
            f"   • Success: {self.success}",
            f"   • Content: {self.content!r}",
            f"   • Model: {self.model}",
            f"   • Elapsed: {self.elapsed_time:.2f}s" if self.elapsed_time is not None else "   • Elapsed: N/A",
        ]


        if self.timestamps:
            td = self.timestamps.to_dict()
            if "generation_requested_at" in td and "generation_completed_at" in td:
                total = td["generation_completed_at"] - td["generation_requested_at"]
                lines.append(f"   • Total Latency: {total} ms")
            if td.get("attempts"):
                first = td["attempts"][0]
                lines.append(f"   • First Invoke: {first['duration_ms']} ms")
                if len(td["attempts"]) > 1:
                    lines.append(f"   • Retries: {len(td['attempts']) - 1}")
                    lines.append(f"   • Total Back-off: {sum(a.get('backoff_after_ms', 0) for a in td['attempts'])} ms")

        if self.meta:
            meta_str = json.dumps(self.meta, indent=4)
            lines.append("   • Meta:")
            for ln in meta_str.splitlines():
                lines.append("     " + ln)

        if self.pipeline_steps_results:
            lines.append("   • Pipeline Steps:")
            for step in self.pipeline_steps_results:
                status = "Success" if step.success else f"Failed ({step.error_message})"
                lines.append(f"     - {step.step_type}: {status}")
        
        # The rest of the fields
        lines.append(f"   • Request ID: {self.request_id}")
        lines.append(f"   • Operation: {self.operation_name}")
        if self.error_message:
            lines.append(f"   • Error: {self.error_message}")
        if self.raw_content and self.raw_content != self.content:
            lines.append("   • Raw Content:")
            lines.append(f"{self.raw_content!r}")
        lines.append(f"   • Formatted Prompt: {self.formatted_prompt!r}")
        lines.append(f"   • Unformatted Prompt: {self.unformatted_prompt!r}")
        lines.append(f"   • Response Type: {self.response_type}")
        lines.append(f"   • Retries: {self.how_many_retries_run}")
        
        return "\n".join(lines)





    # def __str__(self):
    #     result = ["GenerationResult:"]
    #     for field_info in fields(self):
    #         field_name = field_info.name
    #         value = getattr(self, field_name)
    #         field_str = f"{field_name}:"
    #         if isinstance(value, (dict, list)):
    #             field_str += "\n" + indent_text(pprint.pformat(value, indent=4), 4)
    #         elif isinstance(value, str) and '\n' in value:
    #             # Multi-line string, indent each line
    #             field_str += "\n" + indent_text(value, 4)
    #         else:
    #             field_str += f" {value}"
    #         result.append(field_str)
    #     return "\n\n".join(result)




class UsageStats:
    def __init__(self, model=None):
        self.model = model
        self.total_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'input_cost': 0.0,
            'output_cost': 0.0,
            'total_cost': 0.0
        }
        self.operation_usage: Dict[str, Dict[str, float]] = {}

    def update(self, meta, operation_name):
        # Update total usage
        self.total_usage['input_tokens'] += meta.get('input_tokens', 0)
        self.total_usage['output_tokens'] += meta.get('output_tokens', 0)
        self.total_usage['total_tokens'] += meta.get('total_tokens', 0)
        self.total_usage['input_cost'] += meta.get('input_cost', 0.0)
        self.total_usage['output_cost'] += meta.get('output_cost', 0.0)
        self.total_usage['total_cost'] += meta.get('total_cost', 0.0)
        self.total_usage['total_cost'] = round(self.total_usage['total_cost'], 5)

        # Update per-operation usage
        if operation_name not in self.operation_usage:
            self.operation_usage[operation_name] = {
                'input_tokens': 0,
                'output_tokens': 0,
                'total_tokens': 0,
                'input_cost': 0.0,
                'output_cost': 0.0,
                'total_cost': 0.0
            }

        op_usage = self.operation_usage[operation_name]
        op_usage['input_tokens'] += meta.get('input_tokens', 0)
        op_usage['output_tokens'] += meta.get('output_tokens', 0)
        op_usage['total_tokens'] += meta.get('total_tokens', 0)
        op_usage['input_cost'] += meta.get('input_cost', 0.0)
        op_usage['output_cost'] += meta.get('output_cost', 0.0)
        op_usage['total_cost'] += meta.get('total_cost', 0.0)
        op_usage['total_cost'] = round(op_usage['total_cost'], 5)

    def to_dict(self):
        return {
            'model': self.model,
            'total_usage': self.total_usage,
            'operation_usage': self.operation_usage
        }



