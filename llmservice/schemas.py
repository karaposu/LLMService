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
    use_string2dict: bool = False
    operation_name: Optional[str] = None
    postprocess_config: Optional[Dict[str, Any]] = field(default_factory=dict)
    answer_isolator_refinement_config: Optional[Dict[str, Any]] = field(default_factory=dict)
    request_id: Optional[Union[str, int]] = None
    pipeline_config: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class PipelineStepResult:
    step_type: str
    success: bool
    content_before: Any
    content_after: Any
    error_message: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)




@dataclass
class PostprocessingResult:
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    s2d_run_status: bool = False
    s2d_run_result: Optional[Dict[str, Any]] = None
    extract_key_status: bool = False
    extract_key_result: Optional[Any] = None
    string_match_status: bool = False
    string_match_result: Optional[bool] = None
    json_load_status: bool = False
    json_load_result: Optional[Dict[str, Any]] = None
    semantic_isolation: bool = False




# class GenerationResult:
#     success: bool
#     meta: Dict[str, Any] = None  # tokens, cost, etc.
#     content: Optional[str] = None  # result
#     raw_content: Optional[str] = None  # raw result
#     elapsed_time: Optional[int] = None
#     error_message: Optional[str] = None  # rate limits
#     model: Optional[str] = None
#     formatted_prompt: Optional[str] = None  # debug
#     unformatted_prompt: Optional[str] = None  # for debug
#     operation_name: Optional[str] = None
#     request_id: Optional[Union[str, int]] = None
#     response_type: Optional[Literal["json", "str"]] = None
#     number_of_retries: Optional[int] = None  # tenacity data
#     postprocessing_result: Optional[PostprocessingResult] = None


@dataclass
class GenerationResult:
    success: bool
    meta: Dict[str, Any] = field(default_factory=dict)
    raw_content: Optional[str] = None  # Store initial LLM output
    content: Optional[Any] = None      # Final postprocessed content
    elapsed_time: Optional[float] = None
    error_message: Optional[str] = None
    model: Optional[str] = None
    formatted_prompt: Optional[str] = None
    unformatted_prompt: Optional[str] = None
    operation_name: Optional[str] = None
    request_id: Optional[Union[str, int]] = None
    response_type: Optional[str] = None
    number_of_retries: Optional[int] = None
    pipeline_steps_results: List[PipelineStepResult] = field(default_factory=list)

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

    # def __str__(self):
    #     result = ["GenerationResult:"]
    #     for field_info in fields(self):
    #         field_name = field_info.name
    #         value = getattr(self, field_name)
    #         field_str = f"{field_name}: "
    #         if isinstance(value, (dict, list)):
    #             field_str += "\n" + pprint.pformat(value, indent=4)
    #         else:
    #             field_str += str(value)
    #         result.append(field_str)
    #     return "\n".join(result)
