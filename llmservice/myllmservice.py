# myllmservice.py
"""
Clean LLMService implementation that imports prompts from prompts.py.
All prompts are now separated for better maintainability.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from llmservice.base_service import BaseLLMService
from llmservice.schemas import GenerationRequest, GenerationResult

# Import all prompts
from llmservice import prompts

logger = logging.getLogger(__name__)


class MyLLMService(BaseLLMService):
    """
    Custom LLMService implementation with agent-specific methods.
    All prompts are imported from prompts.py.
    """
    
    def __init__(
        self, 
        logger=None, 
        max_concurrent_requests=200,
        default_model_name="gpt-4o-mini",
        thinking_model="o3",
        planning_model="gpt-4o"
    ):
        super().__init__(
            logger=logger or logging.getLogger(__name__),
            default_model_name=default_model_name,
            max_rpm=500,
            max_concurrent_requests=max_concurrent_requests,
        )
        self.thinking_model = thinking_model
        self.planning_model = planning_model
        
        # Style instructions for summarization
        self.style_instructions = {
            "concise": "Be extremely concise, focus only on key points",
            "detailed": "Provide a comprehensive summary with important details",
            "bullets": "Use bullet points for main ideas",
            "narrative": "Write a flowing narrative summary"
        }
    
    # ================================================================
    # Agent Framework LLM Calls
    # ================================================================
    
    def llm_call_for_understand_intent(
        self,
        task: str,
        available_tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Understand user intent and extract task requirements.
        This is the first step in the agent execution loop.
        """
        
        # Format the user prompt
        user_prompt = prompts.UNDERSTAND_INTENT.format(
            task=task,
            context_section=f"Additional Context: {json.dumps(context, indent=2)}" if context else "",
            available_tools=json.dumps(available_tools, indent=2)
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_INTENT_UNDERSTANDING,
            user_prompt=user_prompt,
            model=model or self.default_model_name,
            output_type="json",
            operation_name="understand_intent",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return self.execute_generation(generation_request)
    
    async def async_llm_call_for_understand_intent(
        self,
        task: str,
        available_tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None
    ) -> GenerationResult:
        """Async version of llm_call_for_understand_intent."""
        
        user_prompt = prompts.UNDERSTAND_INTENT.format(
            task=task,
            context_section=f"Additional Context: {json.dumps(context, indent=2)}" if context else "",
            available_tools=json.dumps(available_tools, indent=2)
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_INTENT_UNDERSTANDING,
            user_prompt=user_prompt,
            model=model or self.default_model_name,
            output_type="json",
            operation_name="understand_intent",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return await self.execute_generation_async(generation_request)
    
    def llm_call_for_vague_planning(
        self,
        intent_understanding: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        use_thinking: bool = False,
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Generate multiple high-level approaches to solve the task.
        This explores different strategies before committing to one.
        """
        
        # Use thinking model for complex planning if requested
        if use_thinking:
            model = self.thinking_model
        elif model is None:
            model = self.planning_model
        
        user_prompt = prompts.VAGUE_PLANNING.format(
            intent_understanding=json.dumps(intent_understanding, indent=2),
            available_tools=json.dumps(available_tools, indent=2)
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_PLANNING,
            user_prompt=user_prompt,
            model=model,
            output_type="json",
            operation_name="vague_planning",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return self.execute_generation(generation_request)
    
    async def async_llm_call_for_vague_planning(
        self,
        intent_understanding: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        use_thinking: bool = False,
        model: Optional[str] = None
    ) -> GenerationResult:
        """Async version of vague planning."""
        
        if use_thinking:
            model = self.thinking_model
        elif model is None:
            model = self.planning_model
        
        user_prompt = prompts.VAGUE_PLANNING.format(
            intent_understanding=json.dumps(intent_understanding, indent=2),
            available_tools=json.dumps(available_tools, indent=2)
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_PLANNING,
            user_prompt=user_prompt,
            model=model,
            output_type="json",
            operation_name="vague_planning",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )

        return await self.execute_generation_async(generation_request)
    
    def llm_call_for_deterministic_planning(
        self,
        vague_plans: List[Dict[str, Any]],
        intent_understanding: Dict[str, Any],
        selection_criteria: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Select the best approach and create a detailed execution plan.
        This commits to a specific strategy with concrete expectations.
        """
        
        user_prompt = prompts.DETERMINISTIC_PLANNING.format(
            vague_plans=json.dumps(vague_plans, indent=2),
            intent_understanding=json.dumps(intent_understanding, indent=2),
            selection_criteria_section=f"Selection criteria: {json.dumps(selection_criteria, indent=2)}" if selection_criteria else ""
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_DECISION_MAKING,
            user_prompt=user_prompt,
            model=model or self.planning_model,
            output_type="json",
            operation_name="deterministic_planning",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return self.execute_generation(generation_request)
    
    async def async_llm_call_for_deterministic_planning(
        self,
        vague_plans: List[Dict[str, Any]],
        intent_understanding: Dict[str, Any],
        selection_criteria: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None
    ) -> GenerationResult:
        """Async version of deterministic planning."""
        
        user_prompt = prompts.DETERMINISTIC_PLANNING.format(
            vague_plans=json.dumps(vague_plans, indent=2),
            intent_understanding=json.dumps(intent_understanding, indent=2),
            selection_criteria_section=f"Selection criteria: {json.dumps(selection_criteria, indent=2)}" if selection_criteria else ""
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_DECISION_MAKING,
            user_prompt=user_prompt,
            model=model or self.planning_model,
            output_type="json",
            operation_name="deterministic_planning",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return await self.execute_generation_async(generation_request)
    
    def llm_call_for_action_planning(
        self,
        selected_plan: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Convert the high-level plan into specific executable steps.
        This creates the actual sequence of tool calls and parameters.
        """
        
        user_prompt = prompts.ACTION_PLANNING.format(
            selected_plan=json.dumps(selected_plan, indent=2),
            available_tools=json.dumps(available_tools, indent=2)
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_IMPLEMENTATION,
            user_prompt=user_prompt,
            model=model or self.default_model_name,
            output_type="json",
            operation_name="action_planning",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return self.execute_generation(generation_request)
    
    async def async_llm_call_for_action_planning(
        self,
        selected_plan: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        model: Optional[str] = None
    ) -> GenerationResult:
        """Async version of action planning."""
        
        user_prompt = prompts.ACTION_PLANNING.format(
            selected_plan=json.dumps(selected_plan, indent=2),
            available_tools=json.dumps(available_tools, indent=2)
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_IMPLEMENTATION,
            user_prompt=user_prompt,
            model=model or self.default_model_name,
            output_type="json",
            operation_name="action_planning",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return await self.execute_generation_async(generation_request)
    
    def llm_call_for_execute_step(
        self,
        step_details: Dict[str, Any],
        previous_results: Dict[int, Any],
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Execute a single LLM-based action step.
        This is used when a step requires LLM processing rather than a tool.
        """
        
        # Build the prompt with previous results interpolated
        prompt_template = step_details['parameters'].get('prompt', '')
        
        # Replace placeholders with actual results
        formatted_prompt = prompt_template
        for step_num, result in previous_results.items():
            placeholder = f"{{step_{step_num}_results}}"
            if placeholder in formatted_prompt:
                formatted_prompt = formatted_prompt.replace(
                    placeholder, 
                    json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
                )
        
        generation_request = GenerationRequest(
            user_prompt=formatted_prompt,
            model=model or self.default_model_name,
            operation_name=f"execute_step_{step_details['step_number']}"
        )
        
        return self.execute_generation(generation_request)
    
    async def async_llm_call_for_execute_step(
        self,
        step_details: Dict[str, Any],
        previous_results: Dict[int, Any],
        model: Optional[str] = None
    ) -> GenerationResult:
        """Async version of execute step."""
        
        prompt_template = step_details['parameters'].get('prompt', '')
        formatted_prompt = prompt_template
        
        for step_num, result in previous_results.items():
            placeholder = f"{{step_{step_num}_results}}"
            if placeholder in formatted_prompt:
                formatted_prompt = formatted_prompt.replace(
                    placeholder, 
                    json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
                )
        
        generation_request = GenerationRequest(
            user_prompt=formatted_prompt,
            model=model or self.default_model_name,
            operation_name=f"execute_step_{step_details['step_number']}"
        )
        
        return await self.execute_generation_async(generation_request)
    
    def llm_call_for_evaluate_results(
        self,
        selected_plan: Dict[str, Any],
        execution_results: List[Dict[str, Any]],
        original_intent: Dict[str, Any],
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Evaluate if the execution met the planned expectations.
        Determines success/failure and identifies what went wrong if failed.
        """
        
        user_prompt = prompts.EVALUATE_RESULTS.format(
            original_intent=json.dumps(original_intent, indent=2),
            selected_plan=json.dumps(selected_plan, indent=2),
            execution_results=json.dumps(execution_results, indent=2)
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_EVALUATION,
            user_prompt=user_prompt,
            model=model or self.default_model_name,
            output_type="json",
            operation_name="evaluate_results",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return self.execute_generation(generation_request)
    
    async def async_llm_call_for_evaluate_results(
        self,
        selected_plan: Dict[str, Any],
        execution_results: List[Dict[str, Any]],
        original_intent: Dict[str, Any],
        model: Optional[str] = None
    ) -> GenerationResult:
        """Async version of evaluate results."""
        
        user_prompt = prompts.EVALUATE_RESULTS.format(
            original_intent=json.dumps(original_intent, indent=2),
            selected_plan=json.dumps(selected_plan, indent=2),
            execution_results=json.dumps(execution_results, indent=2)
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_EVALUATION,
            user_prompt=user_prompt,
            model=model or self.default_model_name,
            output_type="json",
            operation_name="evaluate_results",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return await self.execute_generation_async(generation_request)
    
    def llm_call_for_retry_planning(
        self,
        failure_analysis: Dict[str, Any],
        previous_attempts: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Create an updated plan based on failure analysis.
        Learns from what went wrong and adjusts the approach.
        """
        
        user_prompt = prompts.RETRY_PLANNING.format(
            failure_analysis=json.dumps(failure_analysis, indent=2),
            previous_attempts=json.dumps(previous_attempts, indent=2),
            available_tools=json.dumps(available_tools, indent=2)
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_ADAPTIVE,
            user_prompt=user_prompt,
            model=model or self.planning_model,
            output_type="json",
            operation_name="retry_planning",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return self.execute_generation(generation_request)
    
    async def async_llm_call_for_retry_planning(
        self,
        failure_analysis: Dict[str, Any],
        previous_attempts: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        model: Optional[str] = None
    ) -> GenerationResult:
        """Async version of retry planning."""
        
        user_prompt = prompts.RETRY_PLANNING.format(
            failure_analysis=json.dumps(failure_analysis, indent=2),
            previous_attempts=json.dumps(previous_attempts, indent=2),
            available_tools=json.dumps(available_tools, indent=2)
        )

        generation_request = GenerationRequest(
            system_prompt=prompts.SYSTEM_ADAPTIVE,
            user_prompt=user_prompt,
            model=model or self.planning_model,
            output_type="json",
            operation_name="retry_planning",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return await self.execute_generation_async(generation_request)
    
    # ================================================================
    # Utility Methods
    # ================================================================
    
    def llm_call_for_summarize(
        self,
        content: str,
        max_length: int = 200,
        style: str = "concise",
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        General-purpose summarization for use in agents.
        """
        
        user_prompt = prompts.SUMMARIZE.format(
            max_length=max_length,
            style_instruction=self.style_instructions.get(style, style),
            content=content
        )

        generation_request = GenerationRequest(
            user_prompt=user_prompt,
            model=model or self.default_model_name,
            operation_name="summarize"
        )
        
        return self.execute_generation(generation_request)
    
    def llm_call_for_extract_info(
        self,
        content: str,
        info_types: List[str],
        output_format: str = "json",
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Extract specific types of information from content.
        """
        
        user_prompt = prompts.EXTRACT_INFO.format(
            info_types_list=', '.join(info_types),
            content=content,
            output_format=output_format
        )

        pipeline_config = []
        if output_format == "json":
            pipeline_config.append({
                'type': 'ConvertToDict',
                'params': {}
            })

        generation_request = GenerationRequest(
            user_prompt=user_prompt,
            model=model or self.default_model_name,
            output_type=output_format,
            operation_name="extract_info",
            pipeline_config=pipeline_config
        )
        
        return self.execute_generation(generation_request)
    
    def llm_call_for_classify(
        self,
        content: str,
        categories: List[str],
        allow_multiple: bool = False,
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Classify content into predefined categories.
        """
        
        user_prompt = prompts.CLASSIFY.format(
            classification_instruction='one or more' if allow_multiple else 'exactly one',
            categories=json.dumps(categories, indent=2),
            content=content,
            classification_format='["category1", "category2"]' if allow_multiple else '"category"'
        )

        generation_request = GenerationRequest(
            user_prompt=user_prompt,
            model=model or self.default_model_name,
            output_type="json",
            operation_name="classify",
            pipeline_config=[
                {
                    'type': 'ConvertToDict',
                    'params': {}
                }
            ]
        )
        
        return self.execute_generation(generation_request)


# Example usage
def main():
    """Test the agent-specific LLM service methods."""
    
    service = MyLLMService()
    
    # Test intent understanding
    print("=== Testing Intent Understanding ===")
    
    test_task = "Find information about the latest developments in quantum computing and create a summary report"
    test_tools = [
        {"name": "web_search", "description": "Search the web"},
        {"name": "summarize", "description": "Summarize text"}
    ]
    
    result = service.llm_call_for_understand_intent(
        task=test_task,
        available_tools=test_tools
    )
    
    if result.success:
        print(f"Intent understood: {json.dumps(result.content, indent=2)}")
        print(f"Cost: ${result.usage.get('total_cost', 0):.4f}")
    else:
        print(f"Failed: {result.error_message}")
    
    # Test vague planning
    print("\n=== Testing Vague Planning ===")
    
    if result.success:
        planning_result = service.llm_call_for_vague_planning(
            intent_understanding=result.content,
            available_tools=test_tools,
            use_thinking=False  # Set to True to use o3 model
        )
        
        if planning_result.success:
            print(f"Generated {len(planning_result.content)} approaches")
            print(f"Cost: ${planning_result.usage.get('total_cost', 0):.4f}")
            for i, approach in enumerate(planning_result.content):
                print(f"\nApproach {i+1}: {approach['strategy_name']}")
                print(f"Description: {approach['description']}")
    
    # Test summarization
    print("\n=== Testing Summarization ===")
    
    summary_result = service.llm_call_for_summarize(
        content="This is a long text about quantum computing advances in 2024...",
        max_length=50,
        style="bullets"
    )
    
    if summary_result.success:
        print(f"Summary: {summary_result.content}")


if __name__ == "__main__":
    main()