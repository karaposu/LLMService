# schemas.py

from dataclasses import dataclass, field, fields, asdict
from typing import Any, Dict, Optional, Union, Literal , List
import pprint
from datetime import datetime, timezone, timedelta
import json
from textwrap import indent


HEADER = lambda s: f"\033[1m{s}\033[0m" 


def indent_text(text, indent):
    indentation = ' ' * indent
    return '\n'.join(indentation + line for line in text.splitlines())


def _pretty(val, *, indent_level: int = 2) -> str:
    """
    Pretty-print dicts / lists as JSON; everything else via str().
    """
    if isinstance(val, (dict, list)):
        return indent(json.dumps(val, indent=4, ensure_ascii=False), " " * indent_level)
    return str(val)



from enum import Enum

class ErrorType(Enum):
    UNSUPPORTED_REGION       = "unsupported_region"
    INSUFFICIENT_QUOTA       = "insufficient_quota"
    HTTP_429                 = "http_429"
    UNKNOWN_OPENAI_ERROR     = "unknown_openai_error"
    NO_INTERNET_ACCESS       = "no_internet_access"



@dataclass(slots=True)
class BackoffStats:
    # ---- client-side gates ----
    rpm_loops:    int = 0
    rpm_ms:       int = 0
    tpm_loops:    int = 0
    tpm_ms:       int = 0

    # ---- server / retry layer ----
    retry_loops:  int = 0
    retry_ms:     int = 0

    # ---------- convenience helpers ----------- #
    @property
    def client_ms(self) -> int:
        return self.rpm_ms + self.tpm_ms

    @property
    def total_ms(self) -> int:
        return self.client_ms + self.retry_ms


@dataclass
class InvocationAttempt:
    attempt_number:    int
    invoke_start_at:      datetime
    invoke_end_at:        datetime
    backoff_after_ms:  Optional[int] = None
    error_message:     Optional[str] = None


    def duration_ms(self) -> float:
        """Milliseconds spent in this invoke call."""
        return (self.invoke_end_at - self.invoke_start_at).total_seconds() * 1_000
    
    def backoff_ms(self) -> float:
        """Milliseconds of backoff after this attempt (0 if none)."""
        return self.backoff_after_ms.total_seconds() * 1_000 if self.backoff_after_ms else 0.0





@dataclass
class InvokeResponseData:
    """
    Wrapper for a single LLM invoke call (sync or async),
    including all retry attempts and derived metrics.
    """
    success: bool
    response: Any
    usage: Any
    attempts: List[InvocationAttempt] = field(default_factory=list)
  

    # Derived metrics, not passed in by caller
    total_duration_ms: float         = field(init=False)
    attempt_count: int               = field(init=False)
    total_backoff_ms: float          = field(init=False)
    last_error_message: Optional[str]= field(init=False)
    retried: bool                    = field(init=False)

    error_type: Optional[ErrorType] = None

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

    
    generation_requested_at:      Optional[datetime] = None
    generation_enqueued_at:       Optional[datetime] = None
    generation_dequeued_at:       Optional[datetime] = None
   
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

    attempts:                     List[InvocationAttempt] = field(default_factory=list)

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

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize only those fields that are not None.
        """
        data: Dict[str, Any] = {}

        # Only include top‐level timestamps if they’re not None
        if self.generation_requested_at:
            data["generation_requested_at"] = self.generation_requested_at.isoformat()
        if self.generation_enqueued_at:
            data["generation_enqueued_at"] = self.generation_enqueued_at.isoformat()
        if self.generation_dequeued_at:
            data["generation_dequeued_at"] = self.generation_dequeued_at.isoformat()

        # Always include attempts (could be empty, but safe to list)
        data["attempts"] = [
            {
                "n":               a.attempt_number,
                "invoke_start_at": a.invoke_start_at.isoformat(),
                "invoke_end_at":   a.invoke_end_at.isoformat(),
                "duration_ms":     a.duration_ms(),
                "backoff_ms":      a.backoff_ms(),
                "error_message":   a.error_message,
            }
            for a in self.attempts
        ]

        # Derived metrics
        # data["attempt_count"] = self.attempt_count
        # data["retried"]       = self.retried
        data["total_duration_ms"] = self.total_duration_ms
        data["invoke_durations_ms"] = self.invoke_durations_ms
        data["total_backoff_ms"]    = self.total_backoff_ms
        data["postprocessing_duration_ms"] = self.postprocessing_duration_ms

        # Include any explicit step timestamps if not None
        step_fields = [
            "semanticisolation_start_at", "semanticisolation_end_at",
            "converttodict_start_at",     "converttodict_end_at",
            "extractvalue_start_at",      "extractvalue_end_at",
            "stringmatchvalidation_start_at", "stringmatchvalidation_end_at",
            "jsonload_start_at",          "jsonload_end_at"
        ]
        for attr in step_fields:
            ts = getattr(self, attr)
            if ts:
                data[attr] = ts.isoformat()

        # Include postprocessing and generation completed if not None
        if self.postprocessing_completed_at:
            data["postprocessing_completed_at"] = self.postprocessing_completed_at.isoformat()
        if self.generation_completed_at:
            data["generation_completed_at"] = self.generation_completed_at.isoformat()

        return data
    
    def __str__(self) -> str:
        ts_lines: list[str] = []
        for fld in fields(self):
            name  = fld.name
            value = getattr(self, name)
            if isinstance(value, datetime):
                # ISO, keep timezone, trim microseconds to 6-digits:
                ts_lines.append(f"{name}: {value.isoformat()}")
            elif value:                         # non-empty lists etc.
                ts_lines.append(f"{name}: {value}")
        return "\n".join(ts_lines)





@dataclass
class GenerationRequest:
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
    retried:  Optional[Any] = None, 
    attempt_count:  Optional[Any] = None,
    operation_name: Optional[str] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    elapsed_time: Optional[float] = None
    error_message: Optional[str] = None
    model: Optional[str] = None
    formatted_prompt: Optional[str] = None
    unformatted_prompt: Optional[str] = None
    response_type: Optional[str] = None
    pipeline_steps_results: List[PipelineStepResult] = field(default_factory=list)
    # rpm tpm related logs
    rpm_at_the_beginning: Optional[int] = None
    rpm_at_the_end: Optional[int] = None
    tpm_at_the_beginning: Optional[int] = None
    tpm_at_the_end: Optional[int] = None
    rpm_waited: Optional[bool] = None
    rpm_wait_loops: Optional[int] = None
    rpm_waited_ms: Optional[int] = None
    tpm_waited: Optional[bool] = None
    tpm_wait_loops: Optional[int] = None
    tpm_waited_ms: Optional[int] = None
    total_invoke_duration_ms:  Optional[Any] = None, 
    total_backoff_ms: Optional[Any] = None, 
    backoff: BackoffStats = field(default_factory=BackoffStats)

    # detailed timestamp logs  requested_at, enqueued_at... 
    timestamps: Optional[EventTimestamps] = None
    # complete copy of the generation_request
    generation_request: Optional[GenerationRequest] = None



    def __str__(self) -> str:
        lines: list[str] = []
        for f in fields(self):
            name  = f.name
            value = getattr(self, name)

            # ---------- pretty-print dicts & lists ----------------------- #
            if isinstance(value, (dict, list)):
                pretty   = json.dumps(value, indent=4)
                indented = "\n".join("  " + line for line in pretty.splitlines())
                lines.append(f"{name}:\n{indented}")

            # ---------- pretty-print EventTimestamps --------------------- #
            elif isinstance(value, EventTimestamps):
                ts_str   = str(value)                     # already newline-separated
                indented = "\n".join("  " + line for line in ts_str.splitlines())
                lines.append(f"{name}:\n{indented}")

            # ---------- default: show as is ------------------------------ #
            else:
                lines.append(f"{name}: {value}")

        return "\n".join(lines)
    

    # # ---------- pretty-printer ---------- #
    # def __str__(self) -> str:
    #     parts: list[str] = []

    #     # ── quick scalar summary ──────────────────────────────────── #
    #     summary_fields = (
    #         "success", "trace_id", "request_id",
    #         "operation_name", "model", "error_message",
    #         "total_invoke_duration_ms",
    #     )
    #     parts.append(HEADER("▶ Summary"))
    #     for name in summary_fields:
    #         val = getattr(self, name, None)
    #         if val not in (None, [], {}, ""):
    #             parts.append(f"{name}: {val}")

    #     # ── usage --------------------------------------------------- #
    #     if self.usage:
    #         parts.append(HEADER("▶ Usage"))
    #         parts.append(_pretty(self.usage))

    #     # ── back-off stats ----------------------------------------- #
    #     # if any(v for v in vars(self.backoff).values()):
    #     if any(v for v in asdict(self.backoff).values()):
    #         parts.append(HEADER("▶ Back-off"))
    #         # for fname, val in vars(self.backoff).items():
    #         for fname, val in asdict(self.backoff).items():
    #             parts.append(f"{fname}: {val}")
    #         parts.append(f"client_ms: {self.backoff.client_ms}")
    #         parts.append(f"total_ms : {self.backoff.total_ms}")

    #     # ── rate-limit waits --------------------------------------- #
    #     if self.rpm_wait_loops or self.tpm_wait_loops:
    #         parts.append(HEADER("▶ Rate-limit waits"))
    #         parts.append(f"rpm_waited={self.rpm_waited}, loops={self.rpm_wait_loops}, ms={self.rpm_waited_ms}")
    #         parts.append(f"tpm_waited={self.tpm_waited}, loops={self.tpm_wait_loops}, ms={self.tpm_waited_ms}")

    #     # ── timestamps  -------------------------------------------- #
    #     if self.timestamps:
    #         parts.append(HEADER("▶ Timestamps"))
    #         for tname, tval in vars(self.timestamps).items():
    #             if tval:
    #                 parts.append(f"{tname}: {tval}")

    #     # ── pipeline results --------------------------------------- #
    #     if self.pipeline_steps_results:
    #         parts.append(HEADER("▶ Pipeline steps"))
    #         parts.append(_pretty([p.to_dict() for p in self.pipeline_steps_results]))

    #     # ── content ------------------------------------------------- #
    #     if self.raw_content is not None:
    #         parts.append(HEADER("▶ Content"))
    #         parts.append(self.raw_content.strip())

    #     return "\n".join(parts)



    # def __str__(self) -> str:
    #     lines = []
    #     for f in fields(self):
    #         name = f.name
    #         value = getattr(self, name)
            
    #         # For dictionaries or lists, pretty‐print JSON style for readability:
    #         if isinstance(value, (dict, list)):
    #             pretty = json.dumps(value, indent=4)
    #             # Indent each line of the JSON by two spaces
    #             indented = "\n".join("  " + line for line in pretty.splitlines())
    #             lines.append(f"{name}:\n{indented}")
    #         else:
    #             lines.append(f"{name}: {value}")
    #     return "\n".join(lines)
    



    
    # def __str__(self) -> str:
    #     lines = [
    #         f"▶️ GenerationResult:",
    #         f"   • Success: {self.success}",
    #         f"   • Content: {self.content!r}",
    #         f"   • Model: {self.model}",
    #         f"   • Elapsed: {self.elapsed_time:.2f}s" if self.elapsed_time is not None else "   • Elapsed: N/A",
    #     ]


    #     # 1) If EventTimestamps is present, always print a dedicated "Attempts:" block
    #     if self.timestamps:
    #         td = self.timestamps.to_dict()
    #         attempts_list = td.get("attempts", [])

    #         # Print "Attempts:" if at least one InvocationAttempt exists
    #         if attempts_list:
    #             lines.append("   • Attempts:")
    #             for idx, attempt in enumerate(attempts_list, start=1):
    #                 dur = attempt.get("duration_ms", 0.0)
    #                 backoff = attempt.get("backoff_ms", 0.0)
    #                 err = attempt.get("error_message")

    #                 start_iso = attempt.get("invoke_start_at", "")
    #                 end_iso   = attempt.get("invoke_end_at", "")

    #                 lines.append(
    #                     f"     - Attempt {idx}: duration={dur:.2f} ms, "
    #                     f"backoff={backoff:.2f} ms, "
    #                     f"start_at={start_iso}, end_at={end_iso}"
    #                     + (f", error='{err}'" if err else "")
    #                 )

    #             # After listing all, show “First Invoke” & “Retries” summary:
    #             first = attempts_list[0]
    #             dur0 = first.get("duration_ms", 0.0)
    #             lines.append(f"   • First Invoke (duration): {dur0:.2f} ms")

    #             if len(attempts_list) > 1:
    #                 retry_count = len(attempts_list) - 1
    #                 lines.append(f"   • Retries: {retry_count}")
    #                 total_backoff = td.get("total_backoff_ms", 0.0)
    #                 lines.append(f"   • Total Back-off: {total_backoff:.2f} ms")

    #         # 2) Only print “Total Latency” if both generation_requested_at & generation_completed_at exist
    #         if td.get("generation_requested_at") and td.get("generation_completed_at"):
    #             total_ms = td.get("total_duration_ms", 0.0)
    #             lines.append(f"   • Total Latency: {total_ms:.2f} ms")

                 
        
    #     if self.usage:
    #         meta_str = json.dumps(self.usage, indent=4)
    #         lines.append("   • Meta:")
    #         for ln in meta_str.splitlines():
    #             lines.append("     " + ln)

    #     if self.pipeline_steps_results:
    #         lines.append("   • Pipeline Steps:")
    #         for step in self.pipeline_steps_results:
    #             status = "Success" if step.success else f"Failed ({step.error_message})"
    #             lines.append(f"     - {step.step_type}: {status}")
        
    #     # The rest of the fields
    #     lines.append(f"   • Request ID: {self.request_id}")
    #     lines.append(f"   • Operation: {self.operation_name}")
    #     if self.error_message:
    #         lines.append(f"   • Error: {self.error_message}")
    #     if self.raw_content and self.raw_content != self.content:
    #         lines.append("   • Raw Content:")
    #         lines.append(f"{self.raw_content!r}")
    #     lines.append(f"   • Formatted Prompt: {self.formatted_prompt!r}")
    #     lines.append(f"   • Unformatted Prompt: {self.unformatted_prompt!r}")
    #     lines.append(f"   • Response Type: {self.response_type}")
    #     lines.append(f"   • Retries: {self.how_many_retries_run}")
        
    #     return "\n".join(lines)





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



