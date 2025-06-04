# llmservice/bench_service.py  ─────────────────────────────────────────────
from llmservice.base_service import BaseLLMService
from llmservice.schemas      import GenerationRequest, GenerationResult
from typing import Optional, Union

class BenchLLMService(BaseLLMService):
    """
    Each record → two back-to-back completions (lvl-1 then lvl-2),
    mimicking categorize_lvl_by_lvl_async but in a self-contained way.
    """

    MODEL = "gpt-4o-mini"

    # ---- one completion (sync) -----------------------------------------
    def _one_generation_sync(self, seed: str) -> GenerationResult:
        req = GenerationRequest(
            formatted_prompt=f"[sync] dummy prompt {seed}",
            model=self.MODEL,
        )
        return self.execute_generation(req)

    # ---- one completion (async) ----------------------------------------
    async def _one_generation_async(self, seed: str) -> GenerationResult:
        req = GenerationRequest(
            formatted_prompt=f"[async] dummy prompt {seed}",
            model=self.MODEL,
        )
        return await self.execute_generation_async(req)

    # ---- 2-level simulation (sync) -------------------------------------
    def two_lvl_sync(self, seed: str = "x") -> None:
        self._one_generation_sync(f"{seed}-lvl1")
        self._one_generation_sync(f"{seed}-lvl2")

    # ---- 2-level simulation (async) ------------------------------------
    async def two_lvl_async(self, seed: str = "x") -> None:
        await self._one_generation_async(f"{seed}-lvl1")
        await self._one_generation_async(f"{seed}-lvl2")



    def categorize_simple(self,
                               record: str,
                               list_of_classes,
                               request_id: Optional[Union[str, int]] = None) -> GenerationResult:
        
        formatted_prompt = f"""Here is list of classes: {list_of_classes},
        
                            and here is string record to be classified {record}

                            Task Description:
                            Identify the Category: Determine which of the categories the string belongs to.
                            Extra Information - Helpers:  There might be additional information under each subcategory labeled as 'helpers'. These helpers include descs for the taxonomy,  but
                            should be considered as extra information and not directly involved in the classification task
                            Instructions:
                            Given the string record, first identify the category of the given string using given category list,  (your final answer shouldnt include words like "likely").
                            Use the 'Helpers' section for additional context.  And also at the end explain your reasoning in a very short way. 
                            Make sure category is selected from given categories and matches 100%
                            Examples:
                            Record: "Jumper Cable"
                            lvl1: interconnectors
                            
                            Record: "STM32"
                            lvl1: microcontrollers
                             """


        pipeline_config = [
            {
                'type': 'SemanticIsolation',
                'params': {
                    'semantic_element_for_extraction': 'pure category'
                }
            }
        ]

        generation_request = GenerationRequest(
            formatted_prompt=formatted_prompt,
            model="gpt-4o-mini",
            output_type="str",
            operation_name="categorize_simple",
            pipeline_config= pipeline_config,
            request_id=request_id
        )

        generation_result = self.execute_generation(generation_request)

    
        return generation_result
    
    
    async def categorize_simple_async(
        self,
        record: str,
        list_of_classes,
        request_id: Optional[Union[str, int]] = None,
    ) -> GenerationResult:
        """
        Same prompt as categorize_simple, but issued through
        BaseLLMService.execute_generation_async so it can be awaited
        from an asyncio event-loop (e.g. your phase-3 pipeline).
        """
        formatted_prompt = f"""Here is list of classes: {list_of_classes},

                            and here is string record to be classified {record}

                            Task Description:
                            Identify the Category: Determine which of the categories the string belongs to.
                            Extra Information - Helpers:  There might be additional information under each subcategory labeled as 'helpers'. These helpers include descs for the taxonomy,  but
                            should be considered as extra information and not directly involved in the classification task
                            Instructions:
                            Given the string record, first identify the category of the given string using given category list,  (your final answer shouldn't include words like "likely").
                            Use the 'Helpers' section for additional context.  And also at the end explain your reasoning in a very short way. 
                            Make sure category is selected from given categories and matches 100%
                            Examples:
                            Record: "Jumper Cable"
                            lvl1: interconnectors
                            
                            Record: "STM32"
                            lvl1: microcontrollers
        """

        pipeline_config = [
            {
                "type": "SemanticIsolation",
                "params": {"semantic_element_for_extraction": "pure category"},
            }
        ]

        generation_request = GenerationRequest(
            formatted_prompt=formatted_prompt,
            model="gpt-4o-mini",
            output_type="str",
            operation_name="categorize_simple_async",
            pipeline_config=pipeline_config,
            request_id=request_id,
        )

        # BaseLLMService already exposes an async runner:
        result = await self.execute_generation_async(generation_request)
        return result
