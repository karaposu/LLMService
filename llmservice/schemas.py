# schemas.py

from dataclasses import dataclass, field, fields
from typing import Any, Dict, Optional, Union, Literal , List
import pprint

def indent_text(text, indent):
    indentation = ' ' * indent
    return '\n'.join(indentation + line for line in text.splitlines())



@dataclass
class GenerationRequest:

    data_for_placeholders: Dict[str, Any]
    unformatted_prompt: str
    model: Optional[str] = None
    output_type: Literal["json", "str"] = "str"
    operation_name: Optional[str] = None
    request_id: Optional[Union[str, int]] = None
    number_of_retries: Optional[int] = None
    pipeline_config: List[Dict[str, Any]] = field(default_factory=list)
    fail_fallback_value: Optional[str] = None







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


