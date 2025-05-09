# schemas.py

from dataclasses import dataclass, field, fields
from typing import Any, Dict, Optional, Union, Literal , List
import pprint

def indent_text(text, indent):
    indentation = ' ' * indent
    return '\n'.join(indentation + line for line in text.splitlines())




from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union, Literal, List

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



# @dataclass
# class GenerationRequest:
    
#     # formatted_prompt: Optional[str] = None
#     data_for_placeholders: Dict[str, Any]
#     unformatted_prompt: str
#     model: Optional[str] = None
#     output_type: Literal["json", "str"] = "str"
#     operation_name: Optional[str] = None
#     request_id: Optional[Union[str, int]] = None
#     number_of_retries: Optional[int] = None
#     pipeline_config: List[Dict[str, Any]] = field(default_factory=list)
#     fail_fallback_value: Optional[str] = None







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




    def __str__(self):
        result = ["GenerationResult:"]
        for field_info in fields(self):
            field_name = field_info.name
            value = getattr(self, field_name)
            field_str = f"{field_name}:"
            if isinstance(value, (dict, list)):
                field_str += "\n" + indent_text(pprint.pformat(value, indent=4), 4)
            elif isinstance(value, str) and '\n' in value:
                # Multi-line string, indent each line
                field_str += "\n" + indent_text(value, 4)
            else:
                field_str += f" {value}"
            result.append(field_str)
        return "\n\n".join(result)




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



