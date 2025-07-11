# agent_framework/base_agent.py
"""
Base Agent Framework that uses MyLLMService for all LLM operations.
All prompts are now centralized in MyLLMService.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import json
import uuid
from datetime import datetime

# Import the customized LLMService with agent-specific methods
# from myllmservice import MyLLMService
from llmservice.myllmservice import MyLLMService

class AgentState(Enum):
    """States in the agent execution lifecycle."""
    IDLE = "idle"
    UNDERSTANDING_INTENT = "understanding_intent"
    VAGUE_PLANNING = "vague_planning"
    DETERMINISTIC_PLANNING = "deterministic_planning"
    ACTION_PLANNING = "action_planning"
    EXECUTING_ACTION = "executing_action"
    EVALUATING_RESULT = "evaluating_result"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentContext:
    """Context carried throughout the agent execution."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_task: str = ""
    user_context: Optional[Dict[str, Any]] = None
    current_state: AgentState = AgentState.IDLE
    
    # Results from each phase
    intent_understanding: Optional[Dict[str, Any]] = None
    vague_plans: Optional[List[Dict[str, Any]]] = None
    selected_plan: Optional[Dict[str, Any]] = None
    action_steps: Optional[List[Dict[str, Any]]] = None
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    evaluation_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # For tracking results by step number
    step_results: Dict[int, Any] = field(default_factory=dict)
    
    # Retry information
    retry_count: int = 0
    max_retries: int = 3
    retry_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    total_llm_calls: int = 0
    total_cost: float = 0.0
    
    def add_llm_cost(self, cost: float):
        """Track LLM costs across the agent execution."""
        self.total_llm_calls += 1
        self.total_cost += cost


@dataclass
class Tool:
    """Represents a tool available to the agent."""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    is_async: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class BaseAgent(ABC):
    """
    Base class for agents that use MyLLMService.
    All LLM prompts are centralized in MyLLMService.
    """
    
    def __init__(
        self,
        llm_service: MyLLMService = None,
        tools: List[Tool] = None,
        default_model: str = "gpt-4o-mini",
        planning_model: str = "gpt-4o",
        thinking_model: str = "o3",
        use_thinking_for_planning: bool = False,
        verbose: bool = False
    ):
        self.llm_service = llm_service or MyLLMService(
            default_model_name=default_model,
            thinking_model=thinking_model,
            planning_model=planning_model
        )
        self.tools = tools or []
        self.default_model = default_model
        self.planning_model = planning_model
        self.thinking_model = thinking_model
        self.use_thinking_for_planning = use_thinking_for_planning
        self.verbose = verbose
        
        # Tool registry for quick lookup
        self.tool_registry = {tool.name: tool for tool in self.tools}
    
    async def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentContext:
        """
        Main entry point for agent execution.
        Runs through the complete agent loop.
        """
        agent_context = AgentContext(
            original_task=task,
            user_context=context
        )
        
        try:
            # 1. Understand intent
            agent_context.current_state = AgentState.UNDERSTANDING_INTENT
            await self._understand_intent(agent_context)
            
            # 2. Vague planning
            agent_context.current_state = AgentState.VAGUE_PLANNING
            await self._vague_planning(agent_context)
            
            # 3. Deterministic planning
            agent_context.current_state = AgentState.DETERMINISTIC_PLANNING
            await self._deterministic_planning(agent_context)
            
            # 4. Action planning
            agent_context.current_state = AgentState.ACTION_PLANNING
            await self._action_planning(agent_context)
            
            # 5. Execute actions
            agent_context.current_state = AgentState.EXECUTING_ACTION
            await self._execute_actions(agent_context)
            
            # 6. Evaluate results
            agent_context.current_state = AgentState.EVALUATING_RESULT
            evaluation_success = await self._evaluate_results(agent_context)
            
            # 7. Retry if needed
            if not evaluation_success and agent_context.retry_count < agent_context.max_retries:
                agent_context.current_state = AgentState.RETRYING
                return await self._retry_execution(agent_context)
            
            # Complete
            agent_context.current_state = AgentState.COMPLETED
            agent_context.completed_at = datetime.now()
            
        except Exception as e:
            agent_context.current_state = AgentState.FAILED
            agent_context.completed_at = datetime.now()
            if self.verbose:
                print(f"Agent failed with error: {e}")
            raise
        
        return agent_context
    
    async def _understand_intent(self, context: AgentContext):
        """Step 1: Understand user intent and task requirements."""
        if self.verbose:
            print("📋 Understanding intent...")
        
        result = await self.llm_service.async_llm_call_for_understand_intent(
            task=context.original_task,
            available_tools=[t.to_dict() for t in self.tools],
            context=context.user_context,
            model=self.default_model
        )
        
        if result.success:
            context.intent_understanding = result.content
            context.add_llm_cost(result.usage.get('total_cost', 0))
            if self.verbose:
                print(f"✅ Intent understood: {context.intent_understanding.get('main_objective', '')}")
        else:
            raise Exception(f"Failed to understand intent: {result.error_message}")
    
    async def _vague_planning(self, context: AgentContext):
        """Step 2: Generate multiple potential solution approaches."""
        if self.verbose:
            print("🔮 Generating solution approaches...")
        
        result = await self.llm_service.async_llm_call_for_vague_planning(
            intent_understanding=context.intent_understanding,
            available_tools=[t.to_dict() for t in self.tools],
            use_thinking=self.use_thinking_for_planning,
            model=None  # Let the service decide based on use_thinking
        )
        
        if result.success:
            context.vague_plans = result.content
            context.add_llm_cost(result.usage.get('total_cost', 0))
            if self.verbose:
                print(f"✅ Generated {len(context.vague_plans)} approaches:")
                for plan in context.vague_plans:
                    print(f"   - {plan['strategy_name']}: {plan['description']}")
        else:
            raise Exception(f"Failed to generate plans: {result.error_message}")
    
    async def _deterministic_planning(self, context: AgentContext):
        """Step 3: Select the best approach and create a detailed plan."""
        if self.verbose:
            print("🎯 Selecting best approach...")
        
        result = await self.llm_service.async_llm_call_for_deterministic_planning(
            vague_plans=context.vague_plans,
            intent_understanding=context.intent_understanding,
            selection_criteria=self._get_selection_criteria(),
            model=self.planning_model
        )
        
        if result.success:
            context.selected_plan = result.content
            context.add_llm_cost(result.usage.get('total_cost', 0))
            if self.verbose:
                print(f"✅ Selected: {context.selected_plan['selected_approach_name']}")
                print(f"   Reasoning: {context.selected_plan['selection_reasoning']['why_best']}")
        else:
            raise Exception(f"Failed to select plan: {result.error_message}")
    
    async def _action_planning(self, context: AgentContext):
        """Step 4: Break down the plan into concrete executable steps."""
        if self.verbose:
            print("📝 Creating action steps...")
        
        result = await self.llm_service.async_llm_call_for_action_planning(
            selected_plan=context.selected_plan,
            available_tools=[t.to_dict() for t in self.tools],
            model=self.default_model
        )
        
        if result.success:
            context.action_steps = result.content
            context.add_llm_cost(result.usage.get('total_cost', 0))
            if self.verbose:
                print(f"✅ Created {len(context.action_steps)} action steps")
                for step in context.action_steps:
                    deps = f" (depends on {step['depends_on']})" if step['depends_on'] else ""
                    print(f"   {step['step_number']}. {step['tool']}{deps}")
        else:
            raise Exception(f"Failed to create action plan: {result.error_message}")
    
    async def _execute_actions(self, context: AgentContext):
        """Step 5: Execute the planned actions."""
        if self.verbose:
            print("🚀 Executing actions...")
        
        for step in context.action_steps:
            step_num = step['step_number']
            
            if self.verbose:
                print(f"   Step {step_num}: {step['tool']}...")
            
            # Check dependencies
            for dep in step.get('depends_on', []):
                if dep not in context.step_results:
                    raise Exception(f"Step {step_num} depends on step {dep} which hasn't been executed")
            
            # Execute based on action type
            if step['action_type'] == 'tool' and step['tool'] != 'llm':
                # Execute tool
                result = await self._execute_tool_action(step, context)
            else:
                # Execute LLM action
                result = await self._execute_llm_action(step, context)
            
            # Store result for dependent steps
            context.step_results[step_num] = result.get('result') if isinstance(result, dict) else result
            
            if self.verbose and isinstance(result, dict):
                status = "✅" if result.get('success', True) else "❌"
                print(f"   {status} Step {step_num} completed")
    
    async def _execute_tool_action(self, step: Dict[str, Any], context: AgentContext) -> Dict[str, Any]:
        """Execute a tool-based action."""
        tool = self.tool_registry.get(step['tool'])
        
        if not tool:
            return {
                "step": step['step_number'],
                "tool": step['tool'],
                "success": False,
                "error": f"Tool '{step['tool']}' not found"
            }
        
        try:
            # Execute tool with parameters
            if tool.is_async:
                result = await tool.function(**step['parameters'])
            else:
                result = tool.function(**step['parameters'])
            
            execution_result = {
                "step": step['step_number'],
                "tool": step['tool'],
                "success": True,
                "result": result
            }
            context.execution_results.append(execution_result)
            return execution_result
            
        except Exception as e:
            execution_result = {
                "step": step['step_number'],
                "tool": step['tool'],
                "success": False,
                "error": str(e)
            }
            context.execution_results.append(execution_result)
            return execution_result
    
    async def _execute_llm_action(self, step: Dict[str, Any], context: AgentContext) -> Dict[str, Any]:
        """Execute an LLM-based action."""
        result = await self.llm_service.async_llm_call_for_execute_step(
            step_details=step,
            previous_results=context.step_results,
            model=self.default_model
        )
        
        context.add_llm_cost(result.usage.get('total_cost', 0))
        
        execution_result = {
            "step": step['step_number'],
            "tool": "llm",
            "success": result.success,
            "result": result.content if result.success else result.error_message
        }
        context.execution_results.append(execution_result)
        return execution_result
    
    async def _evaluate_results(self, context: AgentContext) -> bool:
        """Step 6: Evaluate if the execution met the planned expectations."""
        if self.verbose:
            print("🔍 Evaluating results...")
        
        result = await self.llm_service.async_llm_call_for_evaluate_results(
            selected_plan=context.selected_plan,
            execution_results=context.execution_results,
            original_intent=context.intent_understanding,
            model=self.default_model
        )
        
        if result.success:
            evaluation = result.content
            context.evaluation_results.append(evaluation)
            context.add_llm_cost(result.usage.get('total_cost', 0))
            
            success = evaluation.get('overall_success', False)
            if self.verbose:
                status = "✅ Success!" if success else "❌ Failed"
                print(f"{status} (Score: {evaluation.get('success_percentage', 0)}%)")
                if not success:
                    print(f"   Recommendation: {evaluation.get('recommendation', 'unknown')}")
            
            return success
        
        return False
    
    async def _retry_execution(self, context: AgentContext) -> AgentContext:
        """Step 7: Retry with lessons learned from failure."""
        context.retry_count += 1
        
        if self.verbose:
            print(f"🔄 Retrying (attempt {context.retry_count}/{context.max_retries})...")
        
        # Store retry information
        context.retry_history.append({
            "retry_number": context.retry_count,
            "failure_reason": context.evaluation_results[-1] if context.evaluation_results else {},
            "previous_execution": context.execution_results.copy()
        })
        
        # Get retry plan
        result = await self.llm_service.async_llm_call_for_retry_planning(
            failure_analysis=context.evaluation_results[-1] if context.evaluation_results else {},
            previous_attempts=context.retry_history,
            available_tools=[t.to_dict() for t in self.tools],
            model=self.planning_model
        )
        
        if result.success:
            context.action_steps = result.content
            context.add_llm_cost(result.usage.get('total_cost', 0))
            
            # Clear execution results for retry
            context.execution_results = []
            context.step_results = {}
            
            # Continue from execution
            await self._execute_actions(context)
            evaluation_success = await self._evaluate_results(context)
            
            if not evaluation_success and context.retry_count < context.max_retries:
                return await self._retry_execution(context)
        
        context.current_state = AgentState.COMPLETED
        context.completed_at = datetime.now()
        return context
    
    # ================================================================
    # Methods that can be overridden by subclasses
    # ================================================================
    
    def _get_selection_criteria(self) -> Optional[Dict[str, Any]]:
        """
        Override this to provide custom selection criteria for planning.
        """
        return None
    
    async def pre_execution_hook(self, context: AgentContext, step: Dict[str, Any]):
        """
        Called before each step execution. Override for custom behavior.
        """
        pass
    
    async def post_execution_hook(self, context: AgentContext, step: Dict[str, Any], result: Dict[str, Any]):
        """
        Called after each step execution. Override for custom behavior.
        """
        pass
    
    def get_summary(self, context: AgentContext) -> Dict[str, Any]:
        """
        Get a summary of the agent execution.
        """
        duration = (context.completed_at - context.started_at).total_seconds() if context.completed_at else None
        
        return {
            "task_id": context.task_id,
            "task": context.original_task,
            "state": context.current_state.value,
            "success": context.current_state == AgentState.COMPLETED,
            "duration_seconds": duration,
            "retry_count": context.retry_count,
            "total_llm_calls": context.total_llm_calls,
            "total_cost": round(context.total_cost, 4),
            "steps_executed": len(context.execution_results),
            "selected_strategy": context.selected_plan.get('selected_approach_name') if context.selected_plan else None
        }


# Example implementation with concrete tools
class ResearchAgent(BaseAgent):
    """Example agent for research tasks with real tool implementations."""
    
    def __init__(self, llm_service: MyLLMService = None, verbose: bool = True):
        # Define research-specific tools
        tools = [
            Tool(
                name="web_search",
                description="Search the web for information",
                parameters={"query": "str", "num_results": "int"},
                function=self._web_search,
                is_async=True
            ),
            Tool(
                name="extract_content",
                description="Extract and clean content from a webpage",
                parameters={"url": "str"},
                function=self._extract_content,
                is_async=True
            ),
            Tool(
                name="save_note",
                description="Save a note or finding",
                parameters={"title": "str", "content": "str", "category": "str"},
                function=self._save_note,
                is_async=False
            )
        ]
        
        super().__init__(
            llm_service=llm_service,
            tools=tools,
            default_model="gpt-4o-mini",
            planning_model="gpt-4o",
            verbose=verbose
        )
        
        self.notes = []  # Store research notes
    
    async def _web_search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """Simulate web search (replace with real implementation)."""
        # In production, use a real search API (Google, Bing, DuckDuckGo, etc.)
        await asyncio.sleep(0.5)  # Simulate API call
        
        return [
            {
                "title": f"Result {i+1} for '{query}'",
                "url": f"https://example.com/result{i+1}",
                "snippet": f"This is a snippet about {query} from result {i+1}..."
            }
            for i in range(num_results)
        ]
    
    async def _extract_content(self, url: str) -> str:
        """Simulate content extraction (replace with real implementation)."""
        # In production, use BeautifulSoup, newspaper3k, or similar
        await asyncio.sleep(0.3)  # Simulate processing
        
        return f"Extracted content from {url}:\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit..."
    
    def _save_note(self, title: str, content: str, category: str) -> Dict[str, Any]:
        """Save a research note."""
        note = {
            "id": len(self.notes) + 1,
            "title": title,
            "content": content,
            "category": category,
            "timestamp": datetime.now().isoformat()
        }
        self.notes.append(note)
        return {"saved": True, "note_id": note["id"]}
    
    def _get_selection_criteria(self) -> Optional[Dict[str, Any]]:
        """Research-specific selection criteria."""
        return {
            "priorities": ["thoroughness", "credibility", "recency"],
            "constraints": ["time_efficient", "cost_effective"],
            "preferences": ["prefer_primary_sources", "include_multiple_perspectives"]
        }


# Example usage
async def example_usage():
    """Demonstrate how to use the agent framework."""
    
    # Create a research agent
    agent = ResearchAgent(verbose=True)
    
    # Run a research task
    context = await agent.run(
        task="Research the latest developments in quantum computing, focusing on practical applications and recent breakthroughs in 2024",
        context={
            "output_format": "detailed_report",
            "max_sources": 10,
            "focus_areas": ["hardware", "algorithms", "applications"]
        }
    )
    
    # Get summary
    summary = agent.get_summary(context)
    print("\n📊 Execution Summary:")
    print(json.dumps(summary, indent=2))
    
    # Access the research notes
    print(f"\n📝 Saved {len(agent.notes)} research notes")
    
    return context


if __name__ == "__main__":
    # Run the example
    import asyncio
    asyncio.run(example_usage())