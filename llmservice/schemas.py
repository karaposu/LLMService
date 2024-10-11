# schemas.py

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union, Literal

@dataclass
class GenerationRequest:
    data_for_placeholders: Dict[str, Any]
    unformatted_prompt: str
    output_type: Literal["json", "str"] = "str"
    use_string2dict: bool = False
    operation_name: Optional[str] = None
    postprocess_config: Optional[Dict[str, Any]] = field(default_factory=dict)
    answer_isolator_refinement_config: Optional[Dict[str, Any]] = field(default_factory=dict)
    request_id: Optional[Union[str, int]] = None


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


@dataclass
class GenerationResult:
    success: bool
    meta: Dict[str, Any] = None  # tokens, cost, etc.
    content: Optional[str] = None  # result
    raw_content: Optional[str] = None  # raw result
    elapsed_time: Optional[int] = None
    error_message: Optional[str] = None  # rate limits
    model: Optional[str] = None
    formatted_prompt: Optional[str] = None  # debug
    unformatted_prompt: Optional[str] = None  # for debug
    operation_name: Optional[str] = None
    request_id: Optional[Union[str, int]] = None
    response_type: Optional[Literal["json", "str"]] = None
    number_of_retries: Optional[int] = None  # tenacity data
    postprocessing_result: Optional[PostprocessingResult] = None
