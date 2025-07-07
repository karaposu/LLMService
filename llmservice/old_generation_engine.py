# generation_engine.py

# to run python -m llmservice.generation_engine

import logging
import time
from typing import Optional, Dict, Any, List, Union,Literal
from dataclasses import dataclass, field
import uuid, time, asyncio

from llmservice.llm_handler import LLMHandler  # Ensure this is correctly imported
from string2dict import String2Dict  # Ensure this is installed and available
from proteas import Proteas  # Ensure this is installed and available
from langchain_core.prompts import PromptTemplate
from langchain_core.prompts.string import get_template_variables

from .schemas import GenerationRequest, GenerationResult,  PipelineStepResult, BackoffStats, LLMCallRequest
from .schemas import EventTimestamps
from .utils import _now_dt

from llmservice.debug_tools import timed 


logger = logging.getLogger(__name__)


class GenerationEngine:
    def __init__(self, llm_handler=None, model_name=None, debug=False):
        self.logger = logging.getLogger(__name__)
        self.debug = debug
        self.s2d = String2Dict()

        if llm_handler:
            self.llm_handler = llm_handler
        else:
            self.llm_handler = LLMHandler(model_name=model_name, logger=self.logger)

        self.proteas = Proteas()

        if self.debug:
            self.logger.setLevel(logging.DEBUG)

        # Define the semantic isolation prompt template
        self.semantic_isolation_prompt_template = """
Here is the text answer which includes the main desired information as well as some additional information: {answer_to_be_refined}
Here is the semantic element which should be used for extraction: {semantic_element_for_extraction}

From the given text answer, isolate and extract the semantic element.
Provide the answer strictly in the following JSON format, do not combine anything, remove all introductory or explanatory text that is not part of the semantic element:

'answer': 'here_is_isolated_answer'
""" 
    
    @staticmethod
    def merge_into_messages(
        system_prompt:   str | None = None,
        user_prompt:     str | None = None,
        assistant_text:  str | None = None,
        input_audio_b64: str | None = None,
        images:          list[str] | None = None,
        tool_call:       dict | None = None,
    ) -> list[tuple[str, object]]:
        """
        Build a LangChain-compatible list[tuple[role, content]].
        Content may be plain text *or* the multimodal dict OpenAI expects.
        """
        msgs: list[tuple[str, object]] = []

        if system_prompt:
            msgs.append(("system", system_prompt))
        if user_prompt and not input_audio_b64:
            msgs.append(("user", user_prompt))
        if assistant_text:
            msgs.append(("assistant", assistant_text))

        # Audio (optionally preceded by user text)
        if input_audio_b64:
            msgs.append(
                (
                    "user",
                    [
                        {"type": "text", "text": user_prompt or ""},
                        {
                            "type": "input_audio",
                            "input_audio": {"data": input_audio_b64, "format": "wav"},
                        },
                    ],
                )
            )

        # Images
        if images:
            for img_b64 in images:
                msgs.append(
                    (
                        "user",
                        [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_b64}"
                                },
                            }
                        ],
                    )
                )

        # Tool / function call
        if tool_call:
            msgs.append(("tool", tool_call))

        if not msgs:
            raise ValueError("merge_into_messages: nothing to send.")
        return msgs
    
    # def _merge_into_messages(req: GenerationRequest) -> list[dict]:
    #     # shortcut for old single-string path
    #     if req.formatted_prompt:
    #         return [{"role": "user", "content": req.formatted_prompt}]

    #     msgs: list[dict] = []

    #     # 1) standard roles
    #     if req.system_prompt:
    #         msgs.append({"role": "system", "content": req.system_prompt})
    #     if req.user_prompt and not req.input_audio_b64:
    #         msgs.append({"role": "user", "content": req.user_prompt})
    #     if req.assistant_text:
    #         msgs.append({"role": "assistant", "content": req.assistant_text})

    #     # 2) audio + optional user text
    #     if req.input_audio_b64:
    #         msgs.append({
    #             "role": "user",
    #             "content": [
    #                 {"type": "text", "text": req.user_prompt or ""},
    #                 {"type": "input_audio",
    #                 "input_audio": {"data": req.input_audio_b64, "format": "wav"}}
    #             ],
    #         })

    #     # 3) images
    #     if req.images:
    #         for img_b64 in req.images:
    #             msgs.append({
    #                 "role": "user",
    #                 "content": [
    #                     {"type": "image_url",
    #                     "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
    #                 ],
    #             })

    #     # 4) tool / function call
    #     if req.tool_call:
    #         msgs.append({"role": "tool", **req.tool_call})

    #     if not msgs:
    #         raise ValueError("GenerationRequest contained no prompt data.")

    #     return msgs

    def _new_trace_id(self) -> str:
        return str(uuid.uuid4())
    
    def _debug(self, message):

        if self.debug:
            self.logger.debug(message)

    def load_prompts(self, yaml_file_path):
        """Loads prompts from a YAML file using Proteas."""
        self.proteas.load_unit_skeletons_from_yaml(yaml_file_path)

    def craft_prompt(self, placeholder_dict: Dict[str, Any], order: Optional[list] = None) -> str:
        """
        Crafts the prompt using Proteas with the given placeholders and order.

        :param placeholder_dict: Dictionary of placeholder values.
        :param order: Optional list specifying the order of units.
        :return: Unformatted prompt string.
        """
        unformatted_prompt = self.proteas.craft(units=order, placeholder_dict=placeholder_dict)
        return unformatted_prompt
    

    
    

    # @timed("invoke_async")
    async def generate_async(
        self,
        formatted_prompt: Optional[str] = None,
        unformatted_template: Optional[str] = None,
        data_for_placeholders: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
        request_id: Optional[Union[str, int]] = None,
        operation_name: Optional[str] = None,

        system_prompt: Optional[str] = None,
        user_prompt : Optional[str] = None,
        input_audio_b64: Optional[str] = None,
        images: Optional[Any] = None,
        tool_call: Optional[Any] = None,

        # output_data_format: Optional[Any] = None,
        output_data_format: Literal["text","audio","both"] = "text",
        audio_output_config: Optional[Any] = None


    ) -> GenerationResult:
        

        if model_name:
           self.llm_handler.change_model(model_name)
        

        invoke_kwargs: Dict[str,Any] = {}
        if output_data_format in ("audio", "both"):
            # if they passed in a custom config use it, otherwise pick our default
            audio_cfg = audio_output_config or {"voice":"alloy","format":"wav"}
            invoke_kwargs["modalities"] = ["text","audio"]
            invoke_kwargs["audio"]      = audio_cfg

        
       
        
        
        

        trace_id = self._new_trace_id()


        prompt_to_send = None
        msgs_dict = None

        if formatted_prompt or unformatted_template:
             prompt_to_send =self.handle_prompt_input_logic(formatted_prompt, unformatted_template, data_for_placeholders)
        if user_prompt or input_audio_b64:

            msgs_dict= self.merge_into_messages(user_prompt=user_prompt,
                                     system_prompt=system_prompt,
                                     input_audio_b64=input_audio_b64,
                                     images=images,
                                     tool_call=tool_call
                                     )
            
        payload = prompt_to_send or msgs_dict     
        
        invoke_response_data = await self.llm_handler.invoke_async(payload,  **invoke_kwargs)
       

        
        response      = invoke_response_data.response
        success       = invoke_response_data.success
        attempts      = invoke_response_data.attempts
        usage         = invoke_response_data.usage
        
        error_type    = invoke_response_data.error_type
       

        total_invoke_duration_ms= invoke_response_data.total_duration_ms
        
        total_backoff_ms=         invoke_response_data.total_backoff_ms
        last_error_message=       invoke_response_data.last_error_message
        retried=                  invoke_response_data.retried
        attempt_count =          invoke_response_data.attempt_count

        actual_retry_loops = max(0, attempt_count - 1)
        backoff = BackoffStats(

            retry_loops = actual_retry_loops,
            retry_ms    = total_backoff_ms
        )

        if not success:
            return GenerationResult(
                success=False,
                trace_id=trace_id,
                usage=usage,
                raw_content=None,
                content=None,

                retried= retried, 
                attempt_count= attempt_count,
                total_invoke_duration_ms= total_invoke_duration_ms, 
                backoff=backoff, 
                # total_backoff_ms=total_backoff_ms, 
                error_message=last_error_message,
               
                model=model_name or self.llm_handler.model_name,
                formatted_prompt=prompt_to_send,
                unformatted_prompt=unformatted_template,
                request_id=request_id,
                operation_name=operation_name,
                timestamps= EventTimestamps( attempts= attempts )
            )

        

        gen_result = GenerationResult(
            success=True,
            trace_id=trace_id,
            usage=usage,
            raw_content=response.content,
            content=None,
            
            retried= retried, 
            attempt_count= attempt_count,
            total_invoke_duration_ms= total_invoke_duration_ms, 
            backoff=backoff, 
            # total_backoff_ms=total_backoff_ms, 
            error_message=last_error_message,
           
            
            model=model_name or self.llm_handler.model_name,
            formatted_prompt=prompt_to_send,
            unformatted_prompt=unformatted_template,
            request_id=request_id,
            operation_name=operation_name,
            timestamps=  EventTimestamps( attempts= attempts )
        )

        return gen_result
    





 # @timed("invoke_sync")      
    def call_llm(
        self,
        llm_call_request,
        request_id,
        operation_name, 
        
    ) -> GenerationResult:
        """
        Generates content using the LLMHandler.

       
        """
        
        trace_id = self._new_trace_id() 
        # model_name=llm_call_request.model_name
        # Enforce either-or contract

         # 1️⃣  If caller asked for a different model, switch in-place
        # if model_name and model_name != self.llm_handler.model_name:
        #     self.llm_handler.change_model(model_name)
        
        # invoke_kwargs: Dict[str,Any] = {}
        # if output_data_format in ("audio", "both"):
        #     # if they passed in a custom config use it, otherwise pick our default
        #     audio_cfg = audio_output_config or {"voice":"alloy","format":"wav"}
        #     invoke_kwargs["modalities"] = ["text","audio"]
        #     invoke_kwargs["audio"]      = audio_cfg


        
        # if formatted_prompt or unformatted_template:
        #     prompt_to_send =self.handle_prompt_input_logic(formatted_prompt, unformatted_template, data_for_placeholders)
        # if user_prompt or input_audio_b64:
        #     msgs_dict= self.merge_into_messages(user_prompt=user_prompt,
        #                                         system_prompt=system_prompt,
        #                                         input_audio_b64=input_audio_b64,
        #                                         images=images,
        #                                         tool_call=tool_call
        #                              )
        
        
        # payload = prompt_to_send or msgs_dict     

        
        invoke_response_data= self.llm_handler.process_call_request(llm_call_request)
        
        # invoke_response_data= self.llm_handler.invoke(llm_call_request)
       
        
        
        r=        invoke_response_data.response
        attempts= invoke_response_data.attempts
        success=  invoke_response_data.success
        usage          = invoke_response_data.usage
        
        error_type    = invoke_response_data.error_type
        
        total_invoke_duration_ms= invoke_response_data.total_duration_ms
        
        total_backoff_ms=         invoke_response_data.total_backoff_ms
        last_error_message=       invoke_response_data.last_error_message
        retried=                  invoke_response_data.retried
        attempt_count =          invoke_response_data.attempt_count

        actual_retry_loops = max(0, attempt_count - 1)
        backoff = BackoffStats(
           
            retry_loops = actual_retry_loops,
            retry_ms    = total_backoff_ms
        )

    
        
        if not  success:
            return GenerationResult(
                success=False,
                trace_id=trace_id,      
                usage=usage,
                raw_content=None,
                content=None,
               
                retried= retried, 
                attempt_count= attempt_count,
                total_invoke_duration_ms= total_invoke_duration_ms, 
                backoff=backoff, 
                # total_backoff_ms=total_backoff_ms, 
                error_message=last_error_message,


                model=self.llm_handler.model_name,
                formatted_prompt=prompt_to_send,
                unformatted_prompt=unformatted_template,
                request_id=request_id,
                operation_name=operation_name, 
                timestamps= EventTimestamps( attempts= attempts )
            )

        return GenerationResult(
            success=True,
            trace_id=trace_id,    
            usage=usage,
            raw_content=r.content,
            content=None,
            
            retried= retried, 
            attempt_count= attempt_count,
            total_invoke_duration_ms= total_invoke_duration_ms, 
            backoff=backoff, 
         #   total_backoff_ms=total_backoff_ms, 
            error_message=last_error_message,
            
            model=self.llm_handler.model_name,
            formatted_prompt=prompt_to_send,
            unformatted_prompt=unformatted_template,
            request_id=request_id,
            operation_name=operation_name, 
            timestamps=  EventTimestamps( attempts= attempts )
        )



 
    async def generate_output_async(
        self,
        generation_request: GenerationRequest
    ) -> GenerationResult:
        
        # 1) Record when this generation was requested (wall‐clock UTC)
        generation_requested_at = _now_dt()
        

        # Unpack the GenerationRequest
        placeholders        = generation_request.data_for_placeholders
        unformatted_prompt  = generation_request.unformatted_prompt
        formatted_prompt    = generation_request.formatted_prompt
        model_name          = generation_request.model or self.llm_handler.model_name
        operation_name      = generation_request.operation_name


        system_prompt      = generation_request.system_prompt
        user_prompt      = generation_request.user_prompt
        input_audio_b64      = generation_request.input_audio_b64
        images      = generation_request.images
        tool_call      = generation_request.tool_call
        
        
        # 1) call the core “generate_async”
        generation_result = await self.generate_async(
            formatted_prompt      = formatted_prompt,
            unformatted_template  = unformatted_prompt,
            data_for_placeholders = placeholders,
            model_name            = model_name,
            request_id            = generation_request.request_id,
            operation_name        = operation_name, 

            system_prompt= system_prompt,
            user_prompt  =  user_prompt,
            input_audio_b64=input_audio_b64,
            images=images, 
            tool_call=tool_call,

        )

        generation_result.generation_request = generation_request


         # Ensure `timestamps` exists and fill in requested time
        if generation_result.timestamps is None:
            generation_result.timestamps = EventTimestamps()
        generation_result.timestamps.generation_requested_at = generation_requested_at

        
        if not generation_result.success:
            return generation_result
        
        # 5) Run any post‐processing pipeline (if configured)
        if generation_request.pipeline_config:
            generation_result = await self.execute_pipeline_async(
                generation_result,
                generation_request.pipeline_config
            )
            # After pipeline finishes, record postprocessing completion time
            generation_result.timestamps.postprocessing_completed_at = _now_dt()
        else:
            # If no pipeline, just set content = raw_content
            generation_result.content = generation_result.raw_content

        # 6) Finally, record when generation fully completed
        generation_result.timestamps.generation_completed_at = _now_dt()

        return generation_result
 
    
    def generate_output(self, generation_request: GenerationRequest) -> GenerationResult:
        """
        Synchronously generates the output and processes postprocessing.

        :param generation_request: GenerationRequest object containing all necessary data.
        :return: GenerationResult object with the output and metadata.
        """
        generation_requested_at= _now_dt()
    
        request_id=generation_request.request_id
        operation_name=generation_request.operation_name

        pipeline_config=generation_request.pipeline_config


        llm_call_request=LLMCallRequest(  
            model_name=         generation_request.model_name,
            system_prompt=      generation_request.system_prompt,
            user_prompt  =      generation_request.user_prompt,
            input_audio_b64=    generation_request.input_audio_b64,
            images=             generation_request.images, 
            tool_call=           generation_request.tool_call,
            output_data_format=  generation_request.output_data_format,
            audio_output_config= generation_request. audio_output_config
            )
        
        
        # Generate the output synchronously
        generation_result = self.call_llm(llm_call_request, request_id, operation_name   )
        
  
        generation_result.timestamps.generation_requested_at= generation_requested_at

        generation_result.generation_request=generation_request

        if not generation_result.success:
            return generation_result

        # Process the output using the pipeline
        if pipeline_config:
            generation_result = self.execute_pipeline(generation_result, pipeline_config)

            generation_result.timestamps.postprocessing_completed_at= _now_dt()
        else:
            # No postprocessing; assign raw_content to content
            generation_result.content = generation_result.raw_content
        
        generation_result.timestamps.generation_completed_at= _now_dt()
       

        return generation_result
    


    def execute_pipeline(self, generation_result: GenerationResult, pipeline_config: List[Dict[str, Any]]) -> GenerationResult:
        """
        Executes the processing pipeline on the generation result.

        :param generation_result: The initial GenerationResult from the LLM.
        :param pipeline_config: List of processing steps.
        :return: Updated GenerationResult after processing.
        """
        current_content = generation_result.raw_content
        for step_config in pipeline_config:
            step_type = step_config.get('type')
            params = step_config.get('params', {})
            method_name = f"process_{step_type.lower()}"
            processing_method = getattr(self, method_name, None)
            step_result = PipelineStepResult(
                step_type=step_type,
                success=False,
                content_before=current_content,
                content_after=None
            )
            if processing_method:
                try:
                    content_after = processing_method(current_content, **params)
                    step_result.success = True
                    step_result.content_after = content_after
                    current_content = content_after  # Update current_content for next step
                except Exception as e:
                    step_result.success = False
                    step_result.error_message = str(e)
                    generation_result.success = False
                    generation_result.error_message = f"Processing step '{step_type}' failed: {e}"
                    self.logger.error(generation_result.error_message)
                    # Record the failed step and exit the pipeline
                    generation_result.pipeline_steps_results.append(step_result)
                    return generation_result
            else:
                step_result.success = False
                error_msg = f"Unknown processing step type: {step_type}"
                step_result.error_message = error_msg
                generation_result.success = False
                generation_result.error_message = error_msg
                self.logger.error(generation_result.error_message)
                # Record the failed step and exit the pipeline
                generation_result.pipeline_steps_results.append(step_result)
                return generation_result
            # Record the successful step
            generation_result.pipeline_steps_results.append(step_result)

        # Update the final content
        generation_result.content = current_content
        return generation_result



    # ------------------------------------------------------------------ #
    #  Async pipeline (run steps sequentially but without blocking)
    # ------------------------------------------------------------------ #
    async def execute_pipeline_async(
        self,
        generation_result: GenerationResult,
        pipeline_config: List[Dict[str, Any]],
    ) -> GenerationResult:
        """
        Asynchronous version of execute_pipeline.
        Every step is awaited *if* an async implementation exists;
        otherwise we fall back to the synchronous one.

        The logic / error handling mirrors the sync function 1-for-1 so the
        calling code can rely on identical behaviour.
        """
        current_content = generation_result.raw_content

        for step_config in pipeline_config:
            step_type   = step_config.get("type")
            params      = step_config.get("params", {})
            async_name  = f"process_{step_type.lower()}_async"
            sync_name   = f"process_{step_type.lower()}"

            # Prefer an async implementation ↓
            processing_method = getattr(self, async_name, None)
            is_async = processing_method is not None and asyncio.iscoroutinefunction(processing_method)

            if not is_async:
                processing_method = getattr(self, sync_name, None)

            step_result = PipelineStepResult(
                step_type      = step_type,
                success        = False,
                content_before = current_content,
                content_after  = None,
            )

            if processing_method is None:
                err_msg = f"Unknown processing step type: {step_type}"
                step_result.error_message = err_msg
                generation_result.success = False
                generation_result.error_message = err_msg
                generation_result.pipeline_steps_results.append(step_result)
                return generation_result

            try:
                # Await async, call sync
                if is_async:
                    content_after = await processing_method(current_content, **params)
                else:
                    content_after = processing_method(current_content, **params)

                step_result.success       = True
                step_result.content_after = content_after
                current_content           = content_after

            except Exception as exc:
                step_result.error_message = str(exc)
                generation_result.success = False
                generation_result.error_message = (
                    f"Processing step '{step_type}' failed: {exc}"
                )
                self.logger.error(generation_result.error_message)
                generation_result.pipeline_steps_results.append(step_result)
                return generation_result

            # Record successful step
            generation_result.pipeline_steps_results.append(step_result)

        # All steps succeeded → update final content
        generation_result.content = current_content
        return generation_result

    


    async def process_semanticisolation_async(
        self,
        content: str,
        *,
        semantic_element_for_extraction: str,
    ) -> str:
        """
        Asynchronous counterpart of `process_semanticisolation`.

        • Builds the same “isolate the semantic element” prompt  
        • Uses *one existing* `GenerationEngine` / `LLMHandler` instance  
        • Awaits `self.generate_async(…)` so the event-loop is never blocked

        Parameters
        ----------
        content : str
            The original LLM answer that contains extra information.
        semantic_element_for_extraction : str
            The specific piece of information we want to isolate (e.g. "pure category").

        Returns
        -------
        str
            The isolated semantic element (e.g. just `"Retail Purchases"`).

        Raises
        ------
        RuntimeError
            If the downstream LLM call fails or the expected key is not found.
        """
        data_for_placeholders = {
            "answer_to_be_refined": content,
            "semantic_element_for_extraction": semantic_element_for_extraction,
        }

        # ---------- launch the SECOND LLM call (non-blocking) ----------
        refine_result = await self.generate_async(
            unformatted_template=self.semantic_isolation_prompt_template,
            data_for_placeholders=data_for_placeholders,
        )

        # ---------- error handling ----------
        if not refine_result.success:
            raise RuntimeError(
                f"Semantic-isolation LLM call failed: {refine_result.error_message}"
            )

        # ---------- parse the JSON-ish string ----------
        try:
            isolated_answer = self.s2d.run(refine_result.raw_content)["answer"]
        except Exception as exc:
            raise RuntimeError(
                f"Could not parse isolation response: {refine_result.raw_content!r}"
            ) from exc

        return isolated_answer

    # Define processing methods
    def process_semanticisolation(self, content: str, semantic_element_for_extraction: str) -> str:
        """
        Processes content using semantic isolation.

        :param content: The content to process.
        :param semantic_element_for_extraction: The semantic element to extract.
        :return: The isolated semantic element.
        """
        answer_to_be_refined = content

        data_for_placeholders = {
            "answer_to_be_refined": answer_to_be_refined,
            "semantic_element_for_extraction": semantic_element_for_extraction,
        }
        unformatted_refiner_prompt = self.semantic_isolation_prompt_template

        refiner_result = self.generate(
            unformatted_template=unformatted_refiner_prompt,
            data_for_placeholders=data_for_placeholders
        )

        if not refiner_result.success:
            raise ValueError(f"Semantic isolation failed: {refiner_result.error_message}")

        # Parse the LLM response to extract 'answer'
        s2d_result = self.s2d.run(refiner_result.raw_content)
        isolated_answer = s2d_result.get('answer')
        if isolated_answer is None:
            raise ValueError("Isolated answer not found in the LLM response.")

        return isolated_answer

    def process_converttodict(self, content: Any) -> Dict[str, Any]:
        """
        Converts content to a dictionary.

        :param content: The content to convert.
        :return: The content as a dictionary.
        """
        if isinstance(content, dict):
            return content  # Already a dict
        return self.s2d.run(content)

    def process_extractvalue(self, content: Dict[str, Any], key: str) -> Any:
        """
        Extracts a value from a dictionary.

        :param content: The dictionary content.
        :param key: The key to extract.
        :return: The extracted value.
        """
        if key not in content:
            raise KeyError(f"Key '{key}' not found in content.")
        return content[key]
    
    # todo add model param for semanticisolation
    def process_stringmatchvalidation(self, content: str, expected_string: str) -> str:
        """
        Validates that the expected string is present in the content.

        :param content: The content to validate.
        :param expected_string: The expected string to find.
        :return: The original content if validation passes.
        """
        if expected_string not in content:
            raise ValueError(f"Expected string '{expected_string}' not found in content.")
        return content

    def process_jsonload(self, content: str) -> Dict[str, Any]:
        """
        Loads content as JSON.

        :param content: The content to load.
        :return: The content as a JSON object.
        """
        import json
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON loading failed: {e}")
        


    def handle_prompt_input_logic(
        self,
        formatted_prompt: Optional[str],
        unformatted_template: Optional[str],
        data_for_placeholders: Optional[Dict[str, Any]]
    ) -> str:
        """
        Ensures exactly one of `formatted_prompt` or (`unformatted_template` + `data_for_placeholders`)
        is provided. If `formatted_prompt` is non‐None, returns it directly. Otherwise, it
        checks that `unformatted_template` and `data_for_placeholders` are both non‐None,
        verifies that no placeholders are missing, and returns the fully‐formatted prompt.

        Raises:
            ValueError if both methods of supplying a prompt are used, or if neither is used,
            or if any placeholders are missing.
        """
        has_formatted = (formatted_prompt is not None)
        has_unformatted = (
            unformatted_template is not None
            and data_for_placeholders is not None
        )

        # 1) Exactly one of the two modes must be used
        if has_formatted and has_unformatted:
            raise ValueError(
                "Provide either `formatted_prompt` or "
                "(`unformatted_template` + `data_for_placeholders`), not both."
            )
        if not (has_formatted or has_unformatted):
            raise ValueError(
                "You must supply either `formatted_prompt` or both "
                "`unformatted_template` and `data_for_placeholders`."
            )

        # 2) If the caller already gave us a fully formatted prompt, just use it
        if has_formatted:
            return formatted_prompt  # type: ignore

        # 3) Otherwise, we have an unformatted template + placeholders. Check for missing keys.
        existing_placeholders = get_template_variables(unformatted_template, "f-string")  # type: ignore
        missing = set(existing_placeholders) - set(data_for_placeholders.keys())  # type: ignore
        if missing:
            raise ValueError(f"Missing data for placeholders: {missing}")

        # 4) Format and return
        tmpl = PromptTemplate.from_template(unformatted_template)  # type: ignore
        return tmpl.format(**data_for_placeholders)  # type: ignore
    
   
    
# Main function for testing
def main():
    import logging

    import sys
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )


    generation_engine = GenerationEngine(model_name='gpt-4o')

    
    formatted_prompt = 'Provide a summary of the following clinical note: Patient shows symptoms of severe headache and nausea.'

    pipeline_config = [
        {
            'type': 'SemanticIsolation',
            'params': {
                'semantic_element_for_extraction': 'symptoms'
            }
        },
        # You can add more steps here if needed
    ]

    gen_request = GenerationRequest(
      
        formatted_prompt=formatted_prompt,
       # pipeline_config=pipeline_config,
        request_id=3,
        operation_name='extract_symptoms'
    )

    generation_result = generation_engine.generate_output(gen_request)

    print(generation_result)

if __name__ == '__main__':
    main()
